from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_matcher.collectors.base import BaseCollector
from job_matcher.collectors.demo import DemoCollector
from job_matcher.collectors.hh import HHCollector
from job_matcher.collectors.hirify import HirifyCollector
from job_matcher.collectors.rabota import RabotaCollector
from job_matcher.collectors.superjob import SuperJobCollector
from job_matcher.collectors.telegram import TelegramCollector
from job_matcher.core.config import Settings
from job_matcher.core.http import ResilientHttpClient
from job_matcher.telegram.tdlib_client import TDLibClient


def build_collectors(
    settings: Settings,
    http_client: ResilientHttpClient,
    tdlib_client: TDLibClient | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> dict[str, BaseCollector]:
    collectors: dict[str, BaseCollector] = {
        "hh": HHCollector(settings, http_client),
        "hirify": HirifyCollector(http_client),
        "superjob": SuperJobCollector(http_client, getattr(settings, "superjob_api_key", "")),
    }
    if settings.telegram_source_enabled and tdlib_client is not None and session_factory is not None:
        collectors["telegram"] = TelegramCollector(settings, tdlib_client, session_factory)
    if settings.enable_experimental_adapters:
        collectors["rabota"] = RabotaCollector(http_client)
    if settings.enable_demo_mode:
        collectors["demo"] = DemoCollector()
    return collectors
