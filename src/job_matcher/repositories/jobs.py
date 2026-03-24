from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from job_matcher.models.job import ApplicationStatus, Job, Notification, UserFeedback
from job_matcher.models.source import SourceError


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, job_id: int) -> Job | None:
        return await self.session.get(Job, job_id)

    async def list_jobs(
        self,
        *,
        status: str | None = None,
        min_score: int | None = None,
        source: str | None = None,
        include_duplicates: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[Job], int]:
        stmt = select(Job)
        count_stmt = select(func.count(Job.id))
        if status:
            stmt = stmt.where(Job.status == status)
            count_stmt = count_stmt.where(Job.status == status)
        if min_score is not None:
            stmt = stmt.where(Job.score >= min_score)
            count_stmt = count_stmt.where(Job.score >= min_score)
        if source:
            stmt = stmt.where(Job.source == source)
            count_stmt = count_stmt.where(Job.source == source)
        if not include_duplicates:
            stmt = stmt.where(Job.duplicate_of_id.is_(None))
            count_stmt = count_stmt.where(Job.duplicate_of_id.is_(None))

        stmt = stmt.order_by(Job.score.desc().nullslast(), Job.published_at.desc().nullslast()).limit(
            limit
        ).offset(offset)
        items = (await self.session.scalars(stmt)).all()
        total = int(await self.session.scalar(count_stmt) or 0)
        return items, total

    async def get_source_counts(self) -> dict[str, int]:
        rows = (
            await self.session.execute(select(Job.source, func.count(Job.id)).group_by(Job.source))
        ).all()
        return {source: int(count) for source, count in rows}

    async def top_matches_count(self, threshold: int) -> int:
        stmt = select(func.count(Job.id)).where(Job.score >= threshold, Job.duplicate_of_id.is_(None))
        return int(await self.session.scalar(stmt) or 0)

    async def duplicate_count(self) -> int:
        stmt = select(func.count(Job.id)).where(Job.duplicate_of_id.is_not(None))
        return int(await self.session.scalar(stmt) or 0)

    async def notifications_sent_count(self) -> int:
        stmt = select(func.count(Notification.id)).where(Notification.status == "sent")
        return int(await self.session.scalar(stmt) or 0)

    async def new_jobs_count(self) -> int:
        stmt = select(func.count(Job.id)).where(Job.status == "new", Job.duplicate_of_id.is_(None))
        return int(await self.session.scalar(stmt) or 0)

    async def total_jobs_count(self) -> int:
        return int(await self.session.scalar(select(func.count(Job.id))) or 0)

    async def add_status(self, job_id: int, status: str, source: str, note: str | None) -> None:
        self.session.add(ApplicationStatus(job_id=job_id, status=status, source=source, note=note))

    async def add_feedback(self, job_id: int, feedback_type: str, value: int = 1) -> None:
        self.session.add(UserFeedback(job_id=job_id, feedback_type=feedback_type, value=value))

    async def add_source_error(
        self, source: str, query: str | None, error_type: str, message: str, context: dict[str, str]
    ) -> None:
        self.session.add(
            SourceError(
                source=source,
                query=query,
                error_type=error_type,
                message=message,
                context=context,
            )
        )
