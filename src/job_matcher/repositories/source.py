from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from job_matcher.core.constants import DEFAULT_SEARCH_QUERIES
from job_matcher.models.source import (
    ScoringProfile,
    SearchQuery,
    SourceCheckpoint,
    TelegramChannel,
    TelegramMessage,
)


class SourceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_default_queries(self, sources: list[str]) -> None:
        existing_rows = (await self.session.execute(select(SearchQuery.source, SearchQuery.query))).all()
        existing_pairs = {(source, query) for source, query in existing_rows}
        for source in ["*", *sources]:
            if source == "telegram":
                continue
            for priority, query in enumerate(DEFAULT_SEARCH_QUERIES, start=1):
                pair = (source, query)
                if pair in existing_pairs:
                    continue
                self.session.add(
                    SearchQuery(source=source, query=query, enabled=True, priority=priority * 10)
                )

    async def ensure_queries(self, source: str, queries: list[str]) -> None:
        existing = (
            await self.session.scalars(select(SearchQuery.query).where(SearchQuery.source == source))
        ).all()
        existing_queries = set(existing)
        for priority, query in enumerate(queries, start=1):
            if query in existing_queries:
                continue
            self.session.add(SearchQuery(source=source, query=query, enabled=True, priority=priority * 10))

    async def get_enabled_queries(self, source: str) -> list[str]:
        specific = (
            await self.session.scalars(
                select(SearchQuery.query)
                .where(SearchQuery.source == source, SearchQuery.enabled.is_(True))
                .order_by(SearchQuery.priority.asc())
            )
        ).all()
        global_queries = (
            await self.session.scalars(
                select(SearchQuery.query)
                .where(SearchQuery.source == "*", SearchQuery.enabled.is_(True))
                .order_by(SearchQuery.priority.asc())
            )
        ).all()
        merged = list(dict.fromkeys([*specific, *global_queries]))
        return merged

    async def touch_checkpoint(
        self,
        source: str,
        query: str,
        *,
        last_attempt_at: datetime,
        last_success_at: datetime | None = None,
        cursor: str | None = None,
        state: dict[str, str] | None = None,
    ) -> None:
        checkpoint = await self.session.scalar(
            select(SourceCheckpoint).where(SourceCheckpoint.source == source, SourceCheckpoint.query == query)
        )
        if checkpoint is None:
            checkpoint = SourceCheckpoint(source=source, query=query)
            self.session.add(checkpoint)
        checkpoint.last_attempt_at = last_attempt_at
        if last_success_at is not None:
            checkpoint.last_success_at = last_success_at
        if cursor is not None:
            checkpoint.cursor = cursor
        if state is not None:
            checkpoint.state = state

    async def upsert_scoring_profile(self, name: str, rules_yaml: str, activate: bool) -> None:
        profile = await self.session.scalar(select(ScoringProfile).where(ScoringProfile.name == name))
        if activate:
            await self.session.execute(update(ScoringProfile).values(is_active=False))
        if profile is None:
            profile = ScoringProfile(name=name, rules_yaml=rules_yaml, is_active=activate)
            self.session.add(profile)
            return
        profile.rules_yaml = rules_yaml
        profile.is_active = activate

    async def get_telegram_channel(self, query: str) -> TelegramChannel | None:
        return await self.session.scalar(select(TelegramChannel).where(TelegramChannel.query == query))

    async def upsert_telegram_channel(
        self,
        *,
        query: str,
        channel_username: str | None,
        channel_title: str | None,
        chat_id: int | None,
        is_private: bool,
        last_message_id: int | None = None,
        last_checked_at: datetime | None = None,
    ) -> TelegramChannel:
        channel = await self.get_telegram_channel(query)
        if channel is None:
            channel = TelegramChannel(query=query)
            self.session.add(channel)
        channel.channel_username = channel_username
        channel.channel_title = channel_title
        channel.chat_id = chat_id
        channel.is_private = is_private
        if last_message_id is not None:
            channel.last_message_id = last_message_id
        if last_checked_at is not None:
            channel.last_checked_at = last_checked_at
        return channel

    async def upsert_telegram_message(
        self,
        *,
        channel: TelegramChannel,
        chat_id: int,
        channel_username: str | None,
        channel_title: str | None,
        message_id: int,
        post_url: str | None,
        posted_at: datetime | None,
        raw_text: str,
        extracted_links: list[str],
        parsed_fields: dict[str, object],
        is_vacancy: bool,
        raw_payload: dict[str, object],
    ) -> TelegramMessage:
        message = await self.session.scalar(
            select(TelegramMessage).where(
                TelegramMessage.chat_id == chat_id,
                TelegramMessage.message_id == message_id,
            )
        )
        if message is None:
            message = TelegramMessage(channel_id=channel.id, chat_id=chat_id, message_id=message_id)
            self.session.add(message)
        message.channel_id = channel.id
        message.channel_username = channel_username
        message.channel_title = channel_title
        message.post_url = post_url
        message.posted_at = posted_at
        message.raw_text = raw_text
        message.extracted_links = extracted_links
        message.parsed_fields = parsed_fields
        message.is_vacancy = is_vacancy
        message.raw_payload = raw_payload
        return message

    async def attach_telegram_message_job(self, chat_id: int, message_id: int, job_id: int) -> None:
        message = await self.session.scalar(
            select(TelegramMessage).where(
                TelegramMessage.chat_id == chat_id,
                TelegramMessage.message_id == message_id,
            )
        )
        if message is not None:
            message.job_id = job_id
