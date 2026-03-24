from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_matcher.models.enums import EmploymentType, ExperienceLevel, RemoteMode
from job_matcher.models.job import Job
from job_matcher.repositories.jobs import JobRepository
from job_matcher.repositories.source import SourceRepository
from job_matcher.schemas.api import StatsResponse
from job_matcher.schemas.domain import NormalizedJob
from job_matcher.scoring.engine import ScoringEngine


@dataclass(slots=True)
class JobService:
    session_factory: async_sessionmaker[AsyncSession]
    scoring_engine: ScoringEngine
    score_threshold: int

    async def list_jobs(
        self,
        *,
        status: str | None,
        min_score: int | None,
        source: str | None,
        include_duplicates: bool,
        limit: int,
        offset: int,
    ) -> tuple[list[Job], int]:
        async with self.session_factory() as session:
            repo = JobRepository(session)
            items, total = await repo.list_jobs(
                status=status,
                min_score=min_score,
                source=source,
                include_duplicates=include_duplicates,
                limit=limit,
                offset=offset,
            )
            return list(items), total

    async def get_job(self, job_id: int) -> Job | None:
        async with self.session_factory() as session:
            return await JobRepository(session).get(job_id)

    async def mark_status(self, job_id: int, status: str, note: str | None, source: str) -> Job:
        async with self.session_factory() as session:
            repo = JobRepository(session)
            job = await repo.get(job_id)
            if job is None:
                raise ValueError(f"job {job_id} not found")
            job.status = status
            await repo.add_status(job_id, status, source, note)
            await session.commit()
            await session.refresh(job)
            return job

    async def add_feedback(self, job_id: int, feedback_type: str, value: int = 1) -> None:
        async with self.session_factory() as session:
            repo = JobRepository(session)
            if await repo.get(job_id) is None:
                raise ValueError(f"job {job_id} not found")
            await repo.add_feedback(job_id, feedback_type, value)
            await session.commit()

    async def rescore_recent_jobs(self, limit: int = 100) -> int:
        async with self.session_factory() as session:
            jobs = (
                await session.scalars(
                    select(Job).order_by(Job.last_seen_at.desc()).limit(limit)
                )
            ).all()
            for job in jobs:
                normalized = self._to_normalized(job)
                score_result = self.scoring_engine.score(normalized)
                job.score = score_result.score
                job.score_reasons = score_result.reasons
                job.score_details = score_result.details
            await session.commit()
            return len(jobs)

    async def get_stats(self) -> StatsResponse:
        async with self.session_factory() as session:
            repo = JobRepository(session)
            return StatsResponse(
                total_jobs=await repo.total_jobs_count(),
                new_jobs=await repo.new_jobs_count(),
                top_matches=await repo.top_matches_count(self.score_threshold),
                duplicates=await repo.duplicate_count(),
                notifications_sent=await repo.notifications_sent_count(),
                source_counts=await repo.get_source_counts(),
            )

    async def update_scoring_profile(self, name: str, rules_yaml: str, activate: bool) -> None:
        yaml.safe_load(StringIO(rules_yaml))
        if activate:
            self.scoring_engine.reload_from_yaml(rules_yaml)
        async with self.session_factory() as session:
            await SourceRepository(session).upsert_scoring_profile(name, rules_yaml, activate)
            await session.commit()

    @staticmethod
    def _to_normalized(job: Job) -> NormalizedJob:
        return NormalizedJob(
            source=job.source,
            external_id=job.external_id,
            source_url=job.source_url,
            canonical_url=job.canonical_url,
            title=job.title,
            company_name=job.company_name,
            city=job.city,
            country=job.country,
            remote_mode=RemoteMode(job.remote_mode),
            employment_type=EmploymentType(job.employment_type),
            experience_level=ExperienceLevel(job.experience_level),
            salary_from=job.salary_from,
            salary_to=job.salary_to,
            salary_currency=job.salary_currency,
            published_at=job.published_at,
            collected_at=job.collected_at,
            description_raw=job.description_raw,
            description_text=job.description_text,
            tech_tags_extracted=job.tech_tags_extracted,
            search_query=job.search_query,
            fingerprint=job.fingerprint,
            language=job.language,
            raw_payload=job.raw_payload,
        )
