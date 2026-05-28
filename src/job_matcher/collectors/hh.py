from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from job_matcher.collectors.base import BaseCollector
from job_matcher.core.config import Settings
from job_matcher.core.http import CircuitOpenError, ResilientHttpClient
from job_matcher.models.enums import EmploymentType
from job_matcher.schemas.domain import CollectorResult, NormalizedJob
from job_matcher.utils.datetime import parse_datetime, utcnow
from job_matcher.utils.extraction import (
    detect_experience_level,
    detect_remote_mode,
    extract_tech_tags,
)
from job_matcher.utils.text import (
    build_fingerprint,
    canonicalize_url,
    normalize_whitespace,
    strip_html,
)

HH_SITE_BASE_URL = "https://hh.ru"
HH_SEARCH_PATH = "/search/vacancy"
HH_CARD_SELECTOR = '[data-qa="vacancy-serp__vacancy"]'
HH_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}
SALARY_NUMBER_RE = re.compile(r"(\d[\d\s\u202f]*)")


class HHCollector(BaseCollector):
    source = "hh"

    def __init__(self, settings: Settings, http_client: ResilientHttpClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def collect(self, query: str) -> CollectorResult:
        try:
            return await self._collect_via_api(query)
        except (CircuitOpenError, httpx.HTTPError):
            return await self._collect_via_html(query)

    async def _collect_via_api(self, query: str) -> CollectorResult:
        headers = {
            "HH-User-Agent": self.settings.http_user_agent,
            "User-Agent": self.settings.http_user_agent,
        }
        payload = await self.http_client.get_json(
            f"{self.settings.hh_api_base_url}/vacancies",
            params={
                "text": query,
                "per_page": 20,
                "order_by": "publication_time",
                "area": 113,
            },
            headers=headers,
        )
        jobs = [self._to_job(item, query) for item in payload.get("items", [])]
        return CollectorResult(
            source=self.source,
            query=query,
            jobs=jobs,
            meta={
                "found": payload.get("found", 0),
                "pages": payload.get("pages", 0),
                "transport": "api",
            },
        )

    async def _collect_via_html(self, query: str) -> CollectorResult:
        html = await self.http_client.get_text(
            f"{HH_SITE_BASE_URL}{HH_SEARCH_PATH}",
            params={
                "text": query,
                "area": 113,
                "order_by": "publication_time",
            },
            headers=HH_DEFAULT_HEADERS,
        )
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(HH_CARD_SELECTOR)

        jobs: list[NormalizedJob] = []
        for card in cards[:20]:
            parsed_card = self._parse_search_card(card)
            if parsed_card is None:
                continue
            detail_html = await self.http_client.get_text(parsed_card["source_url"], headers=HH_DEFAULT_HEADERS)
            parsed_job = self._parse_detail(detail_html, parsed_card, query)
            if parsed_job is not None:
                jobs.append(parsed_job)

        return CollectorResult(
            source=self.source,
            query=query,
            jobs=jobs,
            meta={"found": len(cards), "pages": 1, "transport": "html"},
        )

    def _to_job(self, item: dict[str, Any], query: str) -> NormalizedJob:
        description_text = strip_html(item.get("snippet", {}).get("requirement", ""))
        responsibility = strip_html(item.get("snippet", {}).get("responsibility", ""))
        combined_description = " ".join(part for part in (description_text, responsibility) if part)
        salary = item.get("salary") or {}
        source_url = str(item.get("alternate_url") or item.get("url") or "")
        canonical_url = canonicalize_url(source_url)
        title = item["name"]
        company_name = item.get("employer", {}).get("name") or "Unknown company"
        salary_from = Decimal(str(salary["from"])) if salary.get("from") is not None else None
        salary_to = Decimal(str(salary["to"])) if salary.get("to") is not None else None
        tags = extract_tech_tags([title, combined_description])
        experience_name = item.get("experience", {}).get("name", "")
        return NormalizedJob(
            source=self.source,
            external_id=str(item["id"]),
            source_url=source_url,
            canonical_url=canonical_url,
            title=title,
            company_name=company_name,
            city=item.get("area", {}).get("name"),
            country="Russia",
            remote_mode=detect_remote_mode(title, combined_description),
            employment_type=EmploymentType.FULL_TIME,
            experience_level=detect_experience_level(experience_name, combined_description),
            salary_from=salary_from,
            salary_to=salary_to,
            salary_currency=salary.get("currency"),
            published_at=parse_datetime(item.get("published_at")),
            collected_at=utcnow(),
            description_raw=combined_description,
            description_text=combined_description,
            tech_tags_extracted=tags,
            search_query=query,
            fingerprint=build_fingerprint(
                title,
                company_name,
                str(salary_from or ""),
                str(salary_to or ""),
                combined_description,
            ),
            language="ru",
            raw_payload=item,
        )

    def _parse_search_card(self, card: Tag) -> dict[str, str | None] | None:
        title_node = card.select_one('[data-qa="serp-item__title"]')
        title_text_node = card.select_one('[data-qa="serp-item__title-text"]')
        employer_node = card.select_one('[data-qa="vacancy-serp__vacancy-employer-text"]')
        address_node = card.select_one('[data-qa="vacancy-serp__vacancy-address"]')
        if title_node is None or title_text_node is None:
            return None

        source_url = normalize_whitespace(str(title_node.get("href", "")))
        if not source_url:
            return None
        if source_url.startswith("/"):
            source_url = f"{HH_SITE_BASE_URL}{source_url}"

        external_id = card.find(attrs={"id": True})
        salary_text = self._extract_card_salary_text(card)
        experience = self._extract_card_experience(card)
        return {
            "external_id": normalize_whitespace(str(external_id.get("id", ""))) if external_id else "",
            "source_url": source_url,
            "title": normalize_whitespace(title_text_node.get_text(" ", strip=True)),
            "company_name": normalize_whitespace(employer_node.get_text(" ", strip=True))
            if employer_node
            else "Unknown company",
            "city": normalize_whitespace(address_node.get_text(" ", strip=True)) if address_node else None,
            "salary_text": salary_text,
            "experience": experience,
        }

    def _parse_detail(
        self,
        html: str,
        card_data: dict[str, str | None],
        query: str,
    ) -> NormalizedJob | None:
        soup = BeautifulSoup(html, "html.parser")
        job_posting = self._extract_job_posting(soup)
        raw_description = (
            str(job_posting.get("description", ""))
            if job_posting is not None
            else self._extract_meta_content(soup, "description")
        )
        description_text = strip_html(raw_description)
        title = normalize_whitespace(str(job_posting.get("title", ""))) if job_posting else ""
        if not title:
            title = card_data.get("title") or ""
        company_name = self._extract_company_name(job_posting) or card_data.get("company_name") or "Unknown company"
        city = self._extract_city(job_posting) or card_data.get("city")
        salary_from, salary_to = self._extract_salary(
            card_data.get("salary_text") or self._extract_meta_content(soup, "description")
        )
        experience_hint = card_data.get("experience") or ""
        source_url = card_data.get("source_url") or ""
        tags = extract_tech_tags([title, description_text])

        return NormalizedJob(
            source=self.source,
            external_id=(card_data.get("external_id") or source_url.rstrip("/").split("/")[-1]),
            source_url=source_url,
            canonical_url=canonicalize_url(source_url),
            title=title,
            company_name=company_name,
            city=city,
            country="Russia",
            remote_mode=detect_remote_mode(title, description_text),
            employment_type=EmploymentType.FULL_TIME,
            experience_level=detect_experience_level(experience_hint, description_text),
            salary_from=salary_from,
            salary_to=salary_to,
            salary_currency="RUR" if salary_from is not None or salary_to is not None else None,
            published_at=parse_datetime(self._extract_published_at(job_posting)),
            collected_at=utcnow(),
            description_raw=raw_description,
            description_text=description_text,
            tech_tags_extracted=tags,
            search_query=query,
            fingerprint=build_fingerprint(
                title,
                company_name,
                str(salary_from or ""),
                str(salary_to or ""),
                description_text,
            ),
            language="ru",
            raw_payload={
                "transport": "html",
                "card": card_data,
                "job_posting": job_posting or {},
            },
        )

    @staticmethod
    def _extract_job_posting(soup: BeautifulSoup) -> dict[str, Any] | None:
        for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                payload = json.loads(node.get_text(strip=True))
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("@type") == "JobPosting":
                return payload
        return None

    @staticmethod
    def _extract_meta_content(soup: BeautifulSoup, name: str) -> str:
        tag = soup.find("meta", attrs={"name": name})
        if tag is None:
            return ""
        return normalize_whitespace(str(tag.get("content", "")))

    @staticmethod
    def _extract_company_name(job_posting: dict[str, Any] | None) -> str | None:
        if not job_posting:
            return None
        organization = job_posting.get("hiringOrganization")
        if isinstance(organization, dict):
            return normalize_whitespace(str(organization.get("name", ""))) or None
        return None

    @staticmethod
    def _extract_city(job_posting: dict[str, Any] | None) -> str | None:
        if not job_posting:
            return None
        location = job_posting.get("jobLocation")
        if not isinstance(location, dict):
            return None
        address = location.get("address")
        if not isinstance(address, dict):
            return None
        return normalize_whitespace(str(address.get("addressLocality", ""))) or None

    @staticmethod
    def _extract_published_at(job_posting: dict[str, Any] | None) -> str | None:
        if not job_posting:
            return None
        published_at = job_posting.get("datePosted")
        if not isinstance(published_at, str):
            return None
        return published_at

    @staticmethod
    def _extract_card_salary_text(card: Tag) -> str:
        compensation = card.select_one('[data-qa="vacancy-serp__compensation"]')
        if compensation is not None:
            return normalize_whitespace(compensation.get_text(" ", strip=True))

        for span in card.find_all("span"):
            text = normalize_whitespace(span.get_text(" ", strip=True))
            if "₽" in text or "руб" in text.lower():
                return text
        return ""

    @staticmethod
    def _extract_card_experience(card: Tag) -> str:
        for node in card.find_all(attrs={"data-qa": True}):
            data_qa = str(node.get("data-qa", ""))
            if "work-experience" in data_qa:
                return normalize_whitespace(node.get_text(" ", strip=True))
        return ""

    @staticmethod
    def _extract_salary(value: str | None) -> tuple[Decimal | None, Decimal | None]:
        if not value:
            return None, None
        normalized = normalize_whitespace(value).replace("\u202f", " ")
        numbers = [
            Decimal(match.replace(" ", ""))
            for match in SALARY_NUMBER_RE.findall(normalized)
            if any(char.isdigit() for char in match)
        ]
        if not numbers:
            return None, None
        lowered = normalized.lower()
        if "от" in lowered and "до" not in lowered:
            return numbers[0], None
        if "до" in lowered and "от" not in lowered:
            return None, numbers[0]
        if len(numbers) >= 2:
            return numbers[0], numbers[1]
        return numbers[0], None
