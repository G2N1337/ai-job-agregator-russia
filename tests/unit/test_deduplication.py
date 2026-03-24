from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from job_matcher.db.base import Base
from job_matcher.models.job import Job
from job_matcher.schemas.domain import NormalizedJob
from job_matcher.services.deduplication import DeduplicationService


@pytest.mark.asyncio
async def test_deduplication_finds_existing_by_canonical_url(tmp_path) -> None:
    db_path = tmp_path / "dedup.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        existing = Job(
            source="hh",
            external_id="123",
            source_url="https://example.com/jobs/123",
            canonical_url="https://example.com/jobs/123",
            title="React Developer",
            company_name="Acme",
            city="Remote",
            country="RU",
            remote_mode="remote",
            employment_type="full_time",
            experience_level="middle",
            salary_from=Decimal("200000"),
            salary_to=Decimal("250000"),
            salary_currency="RUB",
            published_at=datetime.now(tz=UTC),
            collected_at=datetime.now(tz=UTC),
            first_seen_at=datetime.now(tz=UTC),
            last_seen_at=datetime.now(tz=UTC),
            description_raw="React Next.js TypeScript",
            description_text="React Next.js TypeScript",
            tech_tags_extracted=["react", "next.js", "typescript"],
            search_query="react developer",
            fingerprint="abc123",
            language="ru",
            score=80,
            score_reasons=[],
            score_details={},
            status="new",
            raw_payload={},
        )
        session.add(existing)
        await session.commit()

        candidate = NormalizedJob(
            source="rabota",
            external_id="999",
            source_url="https://example.com/jobs/123?utm=1",
            canonical_url="https://example.com/jobs/123",
            title="React Developer",
            company_name="Acme",
            city="Remote",
            country="RU",
            remote_mode="remote",
            employment_type="full_time",
            experience_level="middle",
            salary_from=Decimal("200000"),
            salary_to=Decimal("250000"),
            salary_currency="RUB",
            published_at=datetime.now(tz=UTC),
            collected_at=datetime.now(tz=UTC),
            description_raw="React Next.js TypeScript",
            description_text="React Next.js TypeScript",
            tech_tags_extracted=["react", "next.js", "typescript"],
            search_query="react developer",
            fingerprint="another",
            language="ru",
            raw_payload={},
        )

        service = DeduplicationService()
        duplicate = await service.find_duplicate(session, candidate)
        assert duplicate is not None
        assert duplicate.external_id == "123"

    await engine.dispose()
