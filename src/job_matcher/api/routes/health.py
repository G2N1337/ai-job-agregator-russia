from __future__ import annotations

import inspect

from fastapi import APIRouter, Depends
from sqlalchemy import text

from job_matcher.api.dependencies import AppContainer, get_container
from job_matcher.schemas.api import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(container: AppContainer = Depends(get_container)) -> HealthResponse:
    database = "ok"
    redis = "ok"
    scheduler = "running" if container.scheduler_service.scheduler.running else "stopped"

    try:
        async with container.session_factory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        database = "error"

    try:
        ping_result = container.redis_client.ping()
        if inspect.isawaitable(ping_result):
            await ping_result
    except Exception:
        redis = "error"

    status = "ok" if database == "ok" and redis == "ok" else "degraded"
    return HealthResponse(status=status, database=database, redis=redis, scheduler=scheduler)


@router.get("/ready", response_model=HealthResponse)
async def ready(container: AppContainer = Depends(get_container)) -> HealthResponse:
    return await health(container)
