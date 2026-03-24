from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from job_matcher.models.enums import EmploymentType, ExperienceLevel, RemoteMode
from job_matcher.schemas.domain import NormalizedJob
from job_matcher.scoring.engine import ScoringEngine

RULES_PATH = Path("/Users/yan/projects/pet-projects/ai-job-agregator/config/scoring_rules.yaml")


def build_job(title: str, description: str, remote_mode: RemoteMode) -> NormalizedJob:
    now = datetime.now(tz=UTC)
    return NormalizedJob(
        source="demo",
        external_id="1",
        source_url="https://example.com/job/1",
        canonical_url="https://example.com/job/1",
        title=title,
        company_name="Example",
        city="Remote",
        country="RU",
        remote_mode=remote_mode,
        employment_type=EmploymentType.FULL_TIME,
        experience_level=ExperienceLevel.MIDDLE,
        salary_from=Decimal("200000"),
        salary_to=Decimal("280000"),
        salary_currency="RUB",
        published_at=now,
        collected_at=now,
        description_raw=description,
        description_text=description,
        tech_tags_extracted=["typescript", "react", "next.js", "node.js", "nestjs"],
        search_query="fullstack developer",
        fingerprint="fp-1",
        language="ru",
        raw_payload={},
    )


def test_scoring_engine_rewards_matching_stack() -> None:
    engine = ScoringEngine(RULES_PATH)
    result = engine.score(
        build_job(
            "Fullstack Developer",
            "TypeScript React Next.js Node.js NestJS PostgreSQL Redis Docker marketplace AWS",
            RemoteMode.REMOTE,
        )
    )
    assert result.score >= 90
    assert any("TypeScript/React/Next.js match" in reason for reason in result.reasons)


def test_scoring_engine_penalizes_mismatch() -> None:
    engine = ScoringEngine(RULES_PATH)
    result = engine.score(
        build_job(
            "QA Engineer",
            "Manual testing office only Bitrix PHP technical support",
            RemoteMode.OFFICE,
        )
    )
    assert result.score <= 40
    assert any("office-only" in reason for reason in result.reasons)
