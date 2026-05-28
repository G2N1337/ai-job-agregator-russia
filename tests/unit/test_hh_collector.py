from __future__ import annotations

from typing import Any

import httpx
import pytest

from job_matcher.collectors.hh import HHCollector
from job_matcher.core.config import Settings
from job_matcher.core.http import CircuitOpenError


class StubHttpClient:
    def __init__(self) -> None:
        self.api_calls = 0

    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        self.api_calls += 1
        request = httpx.Request("GET", url)
        response = httpx.Response(403, request=request, json={"errors": [{"type": "forbidden"}]})
        raise httpx.HTTPStatusError("forbidden", request=request, response=response)

    async def get_text(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        if "search/vacancy" in url:
            return SEARCH_HTML
        if "vacancy/133559015" in url:
            return DETAIL_HTML
        raise AssertionError(f"unexpected url: {url}")


@pytest.mark.asyncio
async def test_hh_collector_falls_back_to_html_when_api_is_forbidden() -> None:
    collector = HHCollector(Settings(), StubHttpClient())  # type: ignore[arg-type]

    result = await collector.collect("fullstack developer")

    assert result.meta["transport"] == "html"
    assert len(result.jobs) == 1
    assert result.jobs[0].external_id == "133559015"
    assert result.jobs[0].company_name == "Чистякова Анастасия Александровна"
    assert result.jobs[0].salary_from is not None
    assert result.jobs[0].salary_from == 150000
    assert "react" in result.jobs[0].description_text.lower()


class CircuitOpenStubHttpClient(StubHttpClient):
    async def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        raise CircuitOpenError("api.hh.ru blocked")


@pytest.mark.asyncio
async def test_hh_collector_falls_back_to_html_when_circuit_is_open() -> None:
    collector = HHCollector(Settings(), CircuitOpenStubHttpClient())  # type: ignore[arg-type]

    result = await collector.collect("fullstack developer")

    assert result.meta["transport"] == "html"
    assert len(result.jobs) == 1


SEARCH_HTML = """
<div data-qa="vacancy-serp__vacancy">
  <div id="133559015">
    <a data-qa="serp-item__title" href="https://hh.ru/vacancy/133559015?query=fullstack+developer">
      <span data-qa="serp-item__title-text">Frontend-разработчик (международный SaaS / React)</span>
    </a>
    <span>от 150 000 ₽ за месяц</span>
    <span data-qa="vacancy-serp__vacancy-work-experience-between3And6">Опыт 3-6 лет</span>
    <a data-qa="vacancy-serp__vacancy-employer">
      <span data-qa="vacancy-serp__vacancy-employer-text">Чистякова Анастасия Александровна</span>
    </a>
    <span data-qa="vacancy-serp__vacancy-address">Ижевск</span>
  </div>
</div>
"""

DETAIL_HTML = """
<html>
  <head>
    <meta name="description" content="Вакансия Frontend-разработчик. Зарплата: от 150000 ₽ за месяц." />
    <script type="application/ld+json">
      {
        "@context": "https://schema.org/",
        "@type": "JobPosting",
        "description": "<p>React TypeScript REST API</p>",
        "datePosted": "2026-05-27T13:24:00+03:00",
        "title": "Frontend-разработчик (международный SaaS / React)",
        "hiringOrganization": {
          "@type": "Organization",
          "name": "Чистякова Анастасия Александровна"
        },
        "jobLocation": {
          "@type": "Place",
          "address": {
            "@type": "PostalAddress",
            "addressLocality": "Ижевск",
            "addressCountry": "RU"
          }
        }
      }
    </script>
  </head>
  <body></body>
</html>
"""
