from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_matcher.repositories.source import SourceRepository


async def bootstrap_defaults(
    session_factory: async_sessionmaker[AsyncSession],
    sources: list[str],
    telegram_channels: list[str] | None = None,
) -> None:
    async with session_factory() as session:
        repo = SourceRepository(session)
        await repo.ensure_default_queries(sources)
        if telegram_channels:
            await repo.ensure_queries("telegram", telegram_channels)
        await session.commit()
