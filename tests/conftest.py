from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from job_matcher.api.dependencies import AppContainer, build_container
from job_matcher.api.router import api_router
from job_matcher.core.config import Settings
from job_matcher.db.base import Base
from job_matcher.models.job import Job

PROJECT_ROOT = Path("/Users/yan/projects/pet-projects/ai-job-agregator")


@pytest_asyncio.fixture
async def test_container(tmp_path: Path) -> AsyncIterator[AppContainer]:
    db_path = tmp_path / "test.db"
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{db_path}",
        ASYNC_DATABASE_URL=f"sqlite+aiosqlite:///{db_path}",
        REDIS_URL="redis://localhost:6379/15",
        ENABLE_SCHEDULER=False,
        ENABLE_DEMO_MODE=True,
        TELEGRAM_ENABLED=False,
        SCORING_RULES_PATH=PROJECT_ROOT / "config/scoring_rules.yaml",
    )
    engine = create_async_engine(settings.async_database_url, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    container = build_container(settings, session_factory)
    yield container
    await container.http_client.close()
    await container.redis_client.aclose()
    await engine.dispose()


@pytest_asyncio.fixture
async def test_app(test_container: AppContainer) -> FastAPI:
    app = FastAPI()
    app.state.container = test_container
    app.include_router(api_router)
    return app


@pytest_asyncio.fixture
async def seeded_job(test_container: AppContainer) -> Job:
    async with test_container.session_factory() as session:
        job = Job(
            source="demo",
            external_id="demo-1",
            source_url="https://demo.local/jobs/1",
            canonical_url="https://demo.local/jobs/1",
            title="Fullstack Developer",
            company_name="Demo Co",
            city="Remote",
            country="RU",
            remote_mode="remote",
            employment_type="full_time",
            experience_level="middle",
            salary_from=Decimal("200000"),
            salary_to=Decimal("280000"),
            salary_currency="RUB",
            published_at=datetime.now(tz=UTC),
            collected_at=datetime.now(tz=UTC),
            first_seen_at=datetime.now(tz=UTC),
            last_seen_at=datetime.now(tz=UTC),
            description_raw="TypeScript React Next.js Node.js NestJS PostgreSQL Redis Docker",
            description_text="TypeScript React Next.js Node.js NestJS PostgreSQL Redis Docker",
            tech_tags_extracted=["typescript", "react", "next.js", "node.js", "nestjs"],
            search_query="fullstack developer",
            fingerprint="demo-fingerprint",
            language="ru",
            score=88,
            score_reasons=["+20 TypeScript/React/Next.js match"],
            score_details={"matched_keywords": ["typescript", "react", "next.js"]},
            status="new",
            raw_payload={"demo": True},
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job
