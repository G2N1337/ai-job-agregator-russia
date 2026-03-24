from __future__ import annotations

from decimal import Decimal

from job_matcher.collectors.base import BaseCollector
from job_matcher.models.enums import EmploymentType, ExperienceLevel, RemoteMode
from job_matcher.schemas.domain import CollectorResult, NormalizedJob
from job_matcher.utils.datetime import utcnow
from job_matcher.utils.text import build_fingerprint


class DemoCollector(BaseCollector):
    source = "demo"

    async def collect(self, query: str) -> CollectorResult:
        now = utcnow()
        jobs = [
            NormalizedJob(
                source=self.source,
                external_id=f"{query}-001",
                source_url=f"https://demo.local/jobs/{query}-001",
                canonical_url=f"https://demo.local/jobs/{query}-001",
                title="Fullstack Developer (React/Next.js/NestJS)",
                company_name="Demo Marketplace",
                city="Moscow",
                country="Russia",
                remote_mode=RemoteMode.REMOTE,
                employment_type=EmploymentType.FULL_TIME,
                experience_level=ExperienceLevel.MIDDLE_PLUS,
                salary_from=Decimal("250000"),
                salary_to=Decimal("320000"),
                salary_currency="RUB",
                published_at=now,
                collected_at=now,
                description_raw="TypeScript React Next.js Node.js NestJS PostgreSQL Redis Docker AWS marketplace",
                description_text="TypeScript React Next.js Node.js NestJS PostgreSQL Redis Docker AWS marketplace",
                tech_tags_extracted=[
                    "typescript",
                    "react",
                    "next.js",
                    "node.js",
                    "nestjs",
                    "postgresql",
                    "redis",
                    "docker",
                    "aws",
                    "marketplace",
                ],
                search_query=query,
                fingerprint=build_fingerprint(
                    "Fullstack Developer (React/Next.js/NestJS)",
                    "Demo Marketplace",
                    "250000",
                    "320000",
                    "TypeScript React Next.js Node.js NestJS PostgreSQL Redis Docker AWS marketplace",
                ),
                language="ru",
                raw_payload={"demo": True},
            )
        ]
        return CollectorResult(source=self.source, query=query, jobs=jobs)
