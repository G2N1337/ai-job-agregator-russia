from __future__ import annotations

from rapidfuzz import fuzz
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_matcher.models.job import Job
from job_matcher.schemas.domain import NormalizedJob
from job_matcher.utils.text import canonicalize_url, normalize_keyword


class DeduplicationService:
    async def find_duplicate(self, session: AsyncSession, job: NormalizedJob) -> Job | None:
        existing = await session.scalar(
            select(Job).where(Job.source == job.source, Job.external_id == job.external_id)
        )
        if existing is not None:
            return existing

        canonical_url = canonicalize_url(job.canonical_url or job.source_url)
        if canonical_url:
            by_url = await session.scalar(
                select(Job).where(Job.canonical_url == canonical_url).order_by(Job.id.asc())
            )
            if by_url is not None:
                return by_url

        stmt: Select[tuple[Job]] = (
            select(Job)
            .where(Job.fingerprint == job.fingerprint)
            .order_by(Job.id.asc())
            .limit(5)
        )
        candidates = (await session.scalars(stmt)).all()
        if candidates:
            return candidates[0]

        title = normalize_keyword(job.title)
        company = normalize_keyword(job.company_name)
        similar_stmt = (
            select(Job)
            .where(Job.title.ilike(f"%{job.title[:50]}%"))
            .order_by(Job.last_seen_at.desc())
            .limit(20)
        )
        for candidate in (await session.scalars(similar_stmt)).all():
            title_score = fuzz.token_sort_ratio(title, normalize_keyword(candidate.title))
            company_score = fuzz.token_sort_ratio(company, normalize_keyword(candidate.company_name))
            description_score = fuzz.partial_ratio(
                normalize_keyword(job.description_text or ""),
                normalize_keyword(candidate.description_text or ""),
            )
            if title_score >= 88 and company_score >= 80 and description_score >= 72:
                return candidate
        return None
