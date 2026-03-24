from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_matcher.collectors.base import BaseCollector
from job_matcher.core.config import Settings
from job_matcher.models.enums import EmploymentType
from job_matcher.repositories.source import SourceRepository
from job_matcher.schemas.domain import CollectorResult, NormalizedJob
from job_matcher.telegram.tdlib_client import TDLibClient
from job_matcher.utils.datetime import utcnow
from job_matcher.utils.extraction import (
    detect_experience_level,
    detect_remote_mode,
    extract_tech_tags,
)
from job_matcher.utils.text import build_fingerprint, canonicalize_url, normalize_whitespace

URL_RE = re.compile(r"https?://\S+")
VACANCY_HINTS = (
    "вакансия",
    "ищем",
    "developer",
    "frontend",
    "backend",
    "fullstack",
    "react",
    "node",
    "nestjs",
    "typescript",
)
EXTERNAL_JOB_DOMAINS = ("hh.ru", "superjob.ru", "rabota.ru", "greenhouse.io", "lever.co")


class TelegramCollector(BaseCollector):
    source = "telegram"

    def __init__(
        self,
        settings: Settings,
        tdlib_client: TDLibClient,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.settings = settings
        self.tdlib_client = tdlib_client
        self.session_factory = session_factory

    async def collect(self, query: str) -> CollectorResult:
        normalized_query = self._normalize_channel_query(query)
        async with self.session_factory() as session:
            source_repo = SourceRepository(session)
            stored_channel = await source_repo.get_telegram_channel(normalized_query)
            last_message_id = stored_channel.last_message_id if stored_channel else 0

        chat = await self._resolve_chat(normalized_query, stored_channel_chat_id=stored_channel.chat_id if stored_channel else None)
        chat_id = int(chat["id"])
        channel_title = chat.get("title") or normalized_query
        usernames = chat.get("usernames", {})
        channel_username = usernames.get("editable_username") or usernames.get("active_usernames", [None])[0]
        is_private = not bool(channel_username)

        history = await self._collect_new_messages(chat_id=chat_id, last_message_id=last_message_id)
        raw_items: list[dict[str, Any]] = []
        jobs: list[NormalizedJob] = []

        for message in history:
            raw_text = self._extract_message_text(message)
            links = sorted(set(URL_RE.findall(raw_text)))
            post_url = self._build_post_url(channel_username, int(message["id"]))
            parsed_fields = self._parse_message(raw_text, channel_title, links, post_url)
            posted_at = datetime.fromtimestamp(message["date"], tz=UTC) if message.get("date") else None
            raw_items.append(
                {
                    "query": normalized_query,
                    "chat_id": chat_id,
                    "channel_username": channel_username,
                    "channel_title": channel_title,
                    "message_id": int(message["id"]),
                    "post_url": post_url,
                    "posted_at": posted_at,
                    "raw_text": raw_text,
                    "extracted_links": links,
                    "parsed_fields": parsed_fields,
                    "is_vacancy": parsed_fields["is_vacancy"],
                    "is_private": is_private,
                    "raw_payload": message,
                }
            )
            if not parsed_fields["is_vacancy"]:
                continue
            jobs.append(
                self._to_normalized_job(
                    parsed_fields=parsed_fields,
                    query=normalized_query,
                    chat_id=chat_id,
                    message_id=int(message["id"]),
                    posted_at=posted_at,
                    raw_text=raw_text,
                    channel_title=channel_title,
                    channel_username=channel_username,
                    post_url=post_url,
                    links=links,
                )
            )

        latest_message_id = max((int(message["id"]) for message in history), default=last_message_id or 0)
        return CollectorResult(
            source=self.source,
            query=normalized_query,
            jobs=jobs,
            checkpoint_cursor=str(latest_message_id) if latest_message_id else None,
            meta={
                "chat_id": chat_id,
                "channel_title": channel_title,
                "channel_username": channel_username,
                "is_private": is_private,
            },
            raw_items=raw_items,
        )

    async def _resolve_chat(self, query: str, stored_channel_chat_id: int | None) -> dict[str, Any]:
        username = query
        if stored_channel_chat_id:
            try:
                return await self.tdlib_client.get_chat(stored_channel_chat_id)
            except Exception:
                pass
        return await self.tdlib_client.search_public_chat(username)

    async def _collect_new_messages(self, *, chat_id: int, last_message_id: int | None) -> list[dict[str, Any]]:
        newest_first: list[dict[str, Any]] = []
        from_message_id = 0
        for _ in range(5):
            page = await self.tdlib_client.get_chat_history(chat_id=chat_id, from_message_id=from_message_id)
            messages = page.get("messages", [])
            if not messages:
                break
            stop = False
            for message in messages:
                current_id = int(message["id"])
                if last_message_id and current_id <= last_message_id:
                    stop = True
                    break
                newest_first.append(message)
            if stop:
                break
            from_message_id = int(messages[-1]["id"])
        newest_first.sort(key=lambda item: int(item["id"]))
        return newest_first

    @staticmethod
    def _normalize_channel_query(query: str) -> str:
        normalized = query.strip()
        if normalized.startswith("https://t.me/"):
            normalized = normalized.removeprefix("https://t.me/")
        normalized = normalized.removeprefix("@").strip("/")
        if not normalized or "/" in normalized or "+" in normalized:
            raise ValueError(
                "Telegram channel input must be @username or https://t.me/channelusername"
            )
        return normalized

    @staticmethod
    def _extract_message_text(message: dict[str, Any]) -> str:
        content = message.get("content", {})
        text = content.get("text", {})
        formatted = text.get("text")
        if isinstance(formatted, str):
            return normalize_whitespace(formatted)
        return normalize_whitespace(str(content))

    @staticmethod
    def _build_post_url(channel_username: str | None, message_id: int) -> str | None:
        if not channel_username:
            return None
        return f"https://t.me/{channel_username}/{message_id}"

    def _parse_message(
        self, raw_text: str, channel_title: str, links: list[str], post_url: str | None
    ) -> dict[str, object]:
        lower = raw_text.lower()
        is_vacancy = any(hint in lower for hint in VACANCY_HINTS) or any(
            domain in lower for domain in EXTERNAL_JOB_DOMAINS
        )
        title = self._extract_title(raw_text, channel_title)
        company_name = self._extract_company(raw_text, channel_title)
        external_url = next((link for link in links if any(domain in link for domain in EXTERNAL_JOB_DOMAINS)), None)
        return {
            "title": title,
            "company_name": company_name,
            "city": None,
            "country": "Russia",
            "remote_mode": detect_remote_mode(raw_text).value,
            "experience_level": detect_experience_level(title, raw_text).value,
            "employment_type": EmploymentType.FULL_TIME.value,
            "canonical_url": canonicalize_url(external_url or post_url),
            "external_url": external_url,
            "is_vacancy": is_vacancy,
        }

    def _to_normalized_job(
        self,
        *,
        parsed_fields: dict[str, object],
        query: str,
        chat_id: int,
        message_id: int,
        posted_at: datetime | None,
        raw_text: str,
        channel_title: str,
        channel_username: str | None,
        post_url: str | None,
        links: list[str],
    ) -> NormalizedJob:
        title = str(parsed_fields["title"])
        company_name = str(parsed_fields["company_name"])
        source_url = str(parsed_fields["external_url"] or post_url or f"telegram://{chat_id}/{message_id}")
        canonical_url = parsed_fields["canonical_url"]
        tags = extract_tech_tags([title, raw_text])
        return NormalizedJob(
            source=self.source,
            external_id=f"{chat_id}:{message_id}",
            source_url=source_url,
            canonical_url=str(canonical_url) if canonical_url else None,
            title=title,
            company_name=company_name,
            city=None,
            country="Russia",
            remote_mode=detect_remote_mode(raw_text),
            employment_type=EmploymentType.FULL_TIME,
            experience_level=detect_experience_level(title, raw_text),
            salary_from=None,
            salary_to=None,
            salary_currency=None,
            published_at=posted_at,
            collected_at=utcnow(),
            description_raw=raw_text,
            description_text=raw_text,
            tech_tags_extracted=tags,
            search_query=query,
            fingerprint=build_fingerprint(title, company_name, "", "", raw_text),
            language="ru",
            raw_payload={
                "chat_id": chat_id,
                "channel_title": channel_title,
                "channel_username": channel_username,
                "message_id": message_id,
                "post_url": post_url,
                "extracted_links": links,
                "telegram_message_key": f"{chat_id}:{message_id}",
            },
        )

    @staticmethod
    def _extract_title(raw_text: str, fallback: str) -> str:
        first_line = next((line.strip() for line in raw_text.splitlines() if line.strip()), "")
        cleaned = normalize_whitespace(first_line.lstrip("•- ").strip())
        if cleaned:
            return cleaned[:250]
        return fallback

    @staticmethod
    def _extract_company(raw_text: str, fallback: str) -> str:
        for line in raw_text.splitlines():
            normalized = normalize_whitespace(line)
            lower = normalized.lower()
            if lower.startswith("компания:") or lower.startswith("company:"):
                return normalized.split(":", 1)[1].strip() or fallback
        return fallback
