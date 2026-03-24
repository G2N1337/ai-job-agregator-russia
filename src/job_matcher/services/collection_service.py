from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as redis
import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_matcher.collectors.base import BaseCollector
from job_matcher.models.enums import JobStatus
from job_matcher.models.job import Job, JobSnapshot
from job_matcher.repositories.jobs import JobRepository
from job_matcher.repositories.source import SourceRepository
from job_matcher.schemas.domain import CollectorResult, NormalizedJob
from job_matcher.scoring.engine import ScoringEngine
from job_matcher.services.deduplication import DeduplicationService
from job_matcher.services.notification_service import NotificationService
from job_matcher.utils.datetime import utcnow
from job_matcher.utils.location import is_russia

logger = structlog.get_logger(__name__)


@dataclass(slots=True)
class CollectionService:
    session_factory: async_sessionmaker[AsyncSession]
    collectors: dict[str, BaseCollector]
    scoring_engine: ScoringEngine
    dedup_service: DeduplicationService
    notification_service: NotificationService
    redis_client: redis.Redis
    background_tasks: set[asyncio.Task[dict[str, Any]]] = field(default_factory=set)

    async def collect_all(self, source: str | None = None) -> dict[str, Any]:
        target_sources = [source] if source else list(self.collectors.keys())
        results: dict[str, Any] = {}
        for source_name in target_sources:
            if source_name not in self.collectors:
                results[source_name] = {"status": "unknown_source"}
                continue
            results[source_name] = await self.collect_source(source_name)
        return results

    async def collect_source(self, source: str) -> dict[str, Any]:
        lock_key = f"job-matcher:collect:{source}"
        if not await self.redis_client.set(lock_key, "1", ex=900, nx=True):
            return {"status": "skipped", "reason": "already running"}

        try:
            async with self.session_factory() as session:
                source_repo = SourceRepository(session)
                job_repo = JobRepository(session)
                queries = await source_repo.get_enabled_queries(source)
                processed = 0
                created = 0
                duplicates = 0
                notified = 0
                for query in queries:
                    attempt_at = utcnow()
                    try:
                        result = await self.collectors[source].collect(query)
                        await self._persist_raw_items(session, source_repo, result)
                        await source_repo.touch_checkpoint(
                            source,
                            query,
                            last_attempt_at=attempt_at,
                            last_success_at=utcnow(),
                            cursor=result.checkpoint_cursor,
                            state={"jobs": str(len(result.jobs)), **{k: str(v) for k, v in result.meta.items()}},
                        )
                        for normalized_job in result.jobs:
                            if not self._should_keep_job(normalized_job):
                                continue
                            processed += 1
                            job, was_created = await self._upsert_job(session, normalized_job)
                            if was_created:
                                created += 1
                            if job.duplicate_of_id is not None:
                                duplicates += 1
                            if await self.notification_service.notify_if_needed(session, job):
                                notified += 1
                            await self._attach_raw_item_job(session, source_repo, normalized_job, job)
                        await session.commit()
                    except Exception as exc:
                        await source_repo.touch_checkpoint(
                            source, query, last_attempt_at=attempt_at, state={"error": str(exc)}
                        )
                        await job_repo.add_source_error(
                            source,
                            query,
                            type(exc).__name__,
                            str(exc),
                            {"query": query},
                        )
                        await session.commit()
                        logger.exception("collector_failed", source=source, query=query)
                return {
                    "status": "ok",
                    "queries": len(queries),
                    "processed": processed,
                    "created": created,
                    "duplicates": duplicates,
                    "notified": notified,
                }
        finally:
            await self.redis_client.delete(lock_key)

    async def _upsert_job(self, session: AsyncSession, normalized_job: NormalizedJob) -> tuple[Job, bool]:
        duplicate = await self.dedup_service.find_duplicate(session, normalized_job)
        score_result = self.scoring_engine.score(normalized_job)
        now = normalized_job.collected_at
        if duplicate is not None and duplicate.source == normalized_job.source and duplicate.external_id == normalized_job.external_id:
            self._apply_job_update(duplicate, normalized_job, score_result.score, score_result.reasons, score_result.details)
            duplicate.last_seen_at = now
            await self._save_snapshot(session, duplicate, normalized_job.raw_payload, now)
            return duplicate, False

        job = Job(
            source=normalized_job.source,
            external_id=normalized_job.external_id,
            source_url=normalized_job.source_url,
            canonical_url=normalized_job.canonical_url or normalized_job.source_url,
            title=normalized_job.title,
            company_name=normalized_job.company_name,
            city=normalized_job.city,
            country=normalized_job.country,
            remote_mode=normalized_job.remote_mode.value,
            employment_type=normalized_job.employment_type.value,
            experience_level=normalized_job.experience_level.value,
            salary_from=normalized_job.salary_from,
            salary_to=normalized_job.salary_to,
            salary_currency=normalized_job.salary_currency,
            published_at=normalized_job.published_at,
            collected_at=normalized_job.collected_at,
            first_seen_at=now,
            last_seen_at=now,
            description_raw=normalized_job.description_raw,
            description_text=normalized_job.description_text,
            tech_tags_extracted=normalized_job.tech_tags_extracted,
            search_query=normalized_job.search_query,
            fingerprint=normalized_job.fingerprint,
            language=normalized_job.language,
            score=score_result.score,
            score_reasons=score_result.reasons,
            score_details=score_result.details,
            status=JobStatus.NEW.value,
            duplicate_of_id=(duplicate.duplicate_of_id or duplicate.id) if duplicate is not None else None,
            raw_payload=normalized_job.raw_payload,
        )
        session.add(job)
        await session.flush()
        await self._save_snapshot(session, job, normalized_job.raw_payload, now)
        return job, True

    @staticmethod
    def _apply_job_update(
        job: Job,
        normalized_job: NormalizedJob,
        score: int,
        reasons: list[str],
        details: dict[str, Any],
    ) -> None:
        job.source_url = normalized_job.source_url
        job.canonical_url = normalized_job.canonical_url or normalized_job.source_url
        job.title = normalized_job.title
        job.company_name = normalized_job.company_name
        job.city = normalized_job.city
        job.country = normalized_job.country
        job.remote_mode = normalized_job.remote_mode.value
        job.employment_type = normalized_job.employment_type.value
        job.experience_level = normalized_job.experience_level.value
        job.salary_from = normalized_job.salary_from
        job.salary_to = normalized_job.salary_to
        job.salary_currency = normalized_job.salary_currency
        job.published_at = normalized_job.published_at
        job.collected_at = normalized_job.collected_at
        job.description_raw = normalized_job.description_raw
        job.description_text = normalized_job.description_text
        job.tech_tags_extracted = normalized_job.tech_tags_extracted
        job.search_query = normalized_job.search_query
        job.fingerprint = normalized_job.fingerprint
        job.language = normalized_job.language
        job.score = score
        job.score_reasons = reasons
        job.score_details = details
        job.raw_payload = normalized_job.raw_payload

    @staticmethod
    async def _save_snapshot(
        session: AsyncSession, job: Job, payload: dict[str, Any], collected_at: Any
    ) -> None:
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        content_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        session.add(
            JobSnapshot(
                job_id=job.id,
                collected_at=collected_at,
                payload=payload,
                content_hash=content_hash,
            )
        )

    async def collect_in_background(self, source: str | None = None) -> None:
        task = asyncio.create_task(self.collect_all(source))
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    @staticmethod
    def _should_keep_job(normalized_job: NormalizedJob) -> bool:
        if normalized_job.country:
            return is_russia(normalized_job.country)
        return normalized_job.source in {"hh", "superjob", "rabota", "demo"}

    @staticmethod
    async def _persist_raw_items(
        session: AsyncSession,
        source_repo: SourceRepository,
        result: CollectorResult,
    ) -> None:
        if result.source != "telegram":
            return
        raw_items = result.raw_items
        if not raw_items:
            return
        meta = result.meta
        channel = await source_repo.upsert_telegram_channel(
            query=result.query,
            channel_username=meta.get("channel_username"),
            channel_title=meta.get("channel_title"),
            chat_id=meta.get("chat_id"),
            is_private=bool(meta.get("is_private", False)),
            last_message_id=int(result.checkpoint_cursor) if result.checkpoint_cursor else None,
            last_checked_at=utcnow(),
        )
        await session.flush()
        for raw_item in raw_items:
            await source_repo.upsert_telegram_message(
                channel=channel,
                chat_id=int(raw_item["chat_id"]),
                channel_username=raw_item.get("channel_username"),
                channel_title=raw_item.get("channel_title"),
                message_id=int(raw_item["message_id"]),
                post_url=raw_item.get("post_url"),
                posted_at=raw_item.get("posted_at"),
                raw_text=raw_item["raw_text"],
                extracted_links=list(raw_item.get("extracted_links", [])),
                parsed_fields=dict(raw_item.get("parsed_fields", {})),
                is_vacancy=bool(raw_item.get("is_vacancy", False)),
                raw_payload=dict(raw_item.get("raw_payload", {})),
            )

    @staticmethod
    async def _attach_raw_item_job(
        session: AsyncSession,
        source_repo: SourceRepository,
        normalized_job: NormalizedJob,
        job: Job,
    ) -> None:
        if normalized_job.source != "telegram":
            return
        chat_id = normalized_job.raw_payload.get("chat_id")
        message_id = normalized_job.raw_payload.get("message_id")
        if chat_id is None or message_id is None:
            return
        await source_repo.attach_telegram_message_job(int(chat_id), int(message_id), job.id)
