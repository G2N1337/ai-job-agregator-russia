from __future__ import annotations

import pytest

from job_matcher.collectors.telegram import TelegramCollector


def test_normalize_channel_query_supports_username_and_url() -> None:
    assert TelegramCollector._normalize_channel_query("@dev_jobs") == "dev_jobs"
    assert TelegramCollector._normalize_channel_query("https://t.me/dev_jobs") == "dev_jobs"


def test_normalize_channel_query_rejects_invite_links() -> None:
    with pytest.raises(ValueError):
        TelegramCollector._normalize_channel_query("https://t.me/+privateinvite")


def test_parse_message_marks_vacancy_and_prefers_external_job_link() -> None:
    collector = object.__new__(TelegramCollector)
    links = ["https://hh.ru/vacancy/123456"]
    parsed = collector._parse_message(
        raw_text="Вакансия Frontend Developer\nКомпания: Acme\nTypeScript React\nhttps://hh.ru/vacancy/123456",
        channel_title="Dev Jobs",
        links=links,
        post_url="https://t.me/dev_jobs/1",
    )
    assert parsed["is_vacancy"] is True
    assert parsed["company_name"] == "Acme"
    assert parsed["external_url"] == "https://hh.ru/vacancy/123456"
