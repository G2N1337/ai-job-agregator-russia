from __future__ import annotations

from fastapi import APIRouter

from job_matcher.api.routes.health import router as health_router
from job_matcher.api.routes.jobs import router as jobs_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(jobs_router)
