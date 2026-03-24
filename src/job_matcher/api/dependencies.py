from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import redis.asyncio as redis
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_matcher.collectors.registry import build_collectors
from job_matcher.core.config import Settings, get_settings
from job_matcher.core.http import ResilientHttpClient
from job_matcher.scoring.engine import ScoringEngine
from job_matcher.services.collection_service import CollectionService
from job_matcher.services.deduplication import DeduplicationService
from job_matcher.services.job_service import JobService
from job_matcher.services.notification_service import NotificationService
from job_matcher.services.scheduler import SchedulerService
from job_matcher.telegram.bot import TelegramService
from job_matcher.telegram.tdlib_client import TDLibClient


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    session_factory: async_sessionmaker[AsyncSession]
    http_client: ResilientHttpClient
    redis_client: redis.Redis
    scoring_engine: ScoringEngine
    collection_service: CollectionService
    job_service: JobService
    telegram_service: TelegramService
    scheduler_service: SchedulerService


def get_container(request: Request) -> AppContainer:
    return cast(AppContainer, request.app.state.container)


def build_container(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> AppContainer:
    http_client = ResilientHttpClient(settings)
    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    scoring_engine = ScoringEngine(settings.scoring_rules_path)
    dedup_service = DeduplicationService()
    tdlib_client = TDLibClient(settings) if settings.telegram_source_enabled else None
    telegram_service = TelegramService(
        token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        session_factory=session_factory,
    )
    notification_service = NotificationService(
        telegram_service=telegram_service,
        score_threshold=settings.match_score_threshold,
        demo_mode=settings.enable_demo_mode,
    )
    collectors = build_collectors(settings, http_client, tdlib_client, session_factory)
    collection_service = CollectionService(
        session_factory=session_factory,
        collectors=collectors,
        scoring_engine=scoring_engine,
        dedup_service=dedup_service,
        notification_service=notification_service,
        redis_client=redis_client,
    )
    job_service = JobService(
        session_factory=session_factory,
        scoring_engine=scoring_engine,
        score_threshold=settings.match_score_threshold,
    )
    scheduler_service = SchedulerService(
        scheduler=AsyncIOScheduler(timezone=settings.tz),
        collection_service=collection_service,
        interval_minutes=settings.collect_interval_minutes,
    )
    return AppContainer(
        settings=settings,
        session_factory=session_factory,
        http_client=http_client,
        redis_client=redis_client,
        scoring_engine=scoring_engine,
        collection_service=collection_service,
        job_service=job_service,
        telegram_service=telegram_service,
        scheduler_service=scheduler_service,
    )


def get_settings_dependency() -> Settings:
    return get_settings()
