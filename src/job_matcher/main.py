from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from job_matcher.api.dependencies import build_container
from job_matcher.api.router import api_router
from job_matcher.core.config import get_settings, get_telegram_source_channels
from job_matcher.core.logging import configure_logging
from job_matcher.db.session import AsyncSessionLocal
from job_matcher.services.bootstrap import bootstrap_defaults

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container = build_container(settings, AsyncSessionLocal)
    app.state.container = container
    await bootstrap_defaults(
        AsyncSessionLocal,
        [
            name
            for name in container.collection_service.collectors.keys()
            if name not in {"demo", "telegram"}
        ],
        telegram_channels=get_telegram_source_channels(settings),
    )
    if settings.telegram_enabled:
        await container.telegram_service.start()
    if settings.enable_scheduler:
        container.scheduler_service.start()
    yield
    container.scheduler_service.stop()
    await container.telegram_service.stop()
    await container.http_client.close()
    await container.redis_client.aclose()


app = FastAPI(
    title="AI Job Aggregator",
    version="0.1.0",
    description="Collects, scores, deduplicates and notifies about matching jobs.",
    lifespan=lifespan,
)
app.include_router(api_router)
