from __future__ import annotations

import re
from decimal import Decimal

from bs4 import BeautifulSoup

from job_matcher.collectors.base import BaseCollector
from job_matcher.core.http import ResilientHttpClient
from job_matcher.models.enums import EmploymentType
from job_matcher.schemas.domain import CollectorResult, NormalizedJob
from job_matcher.utils.datetime import utcnow
from job_matcher.utils.extraction import (
    detect_experience_level,
    detect_remote_mode,
    extract_tech_tags,
)
from job_matcher.utils.text import build_fingerprint, canonicalize_url, normalize_whitespace


class RabotaCollector(BaseCollector):
    source = "rabota"
    experimental = True

    def __init__(self, http_client: ResilientHttpClient) -> None:
        self.http_client = http_client

    async def collect(self, query: str) -> CollectorResult:
        html = await self.http_client.get_text("https://www.rabota.ru/vacancy", params={"query": query})
        links = re.findall(r'href="(/vacancy/\d+/)', html)
        unique_links: list[str] = []
        for link in links:
            full_url = f"https://www.rabota.ru{link}"
            if full_url not in unique_links:
                unique_links.append(full_url)
        jobs: list[NormalizedJob] = []
        for url in unique_links[:10]:
            detail = await self.http_client.get_text(url)
            parsed = self._parse_detail(detail, url, query)
            if parsed is not None:
                jobs.append(parsed)
        return CollectorResult(source=self.source, query=query, jobs=jobs)

    def _parse_detail(self, html: str, url: str, query: str) -> NormalizedJob | None:
        soup = BeautifulSoup(html, "html.parser")
        title_tag = soup.find("meta", attrs={"property": "og:title"})
        description_tag = soup.find("meta", attrs={"name": "description"})
        if title_tag is None:
            return None
        title_content = str(title_tag.get("content", ""))
        title = normalize_whitespace(title_content.split(" в ", 1)[0].replace("Вакансия ", ""))
        description = (
            normalize_whitespace(str(description_tag.get("content", "")))
            if description_tag
            else ""
        )
        page_text = normalize_whitespace(" ".join(soup.stripped_strings))
        company_name = self._extract_company(title_content)
        salary_from, salary_to = self._extract_salary(title_content)

        return NormalizedJob(
            source=self.source,
            external_id=url.rstrip("/").split("/")[-1],
            source_url=url,
            canonical_url=canonicalize_url(url),
            title=title,
            company_name=company_name,
            city=self._extract_city(title_content),
            country="Russia",
            remote_mode=detect_remote_mode(title_content, description, page_text),
            employment_type=EmploymentType.FULL_TIME,
            experience_level=detect_experience_level(title, page_text),
            salary_from=salary_from,
            salary_to=salary_to,
            salary_currency="RUB" if salary_from or salary_to else None,
            published_at=utcnow(),
            collected_at=utcnow(),
            description_raw=description,
            description_text=page_text,
            tech_tags_extracted=extract_tech_tags([title, description, page_text]),
            search_query=query,
            fingerprint=build_fingerprint(
                title,
                company_name,
                str(salary_from or ""),
                str(salary_to or ""),
                page_text,
            ),
            language="ru",
            raw_payload={"url": url},
        )

    @staticmethod
    def _extract_company(title_content: str) -> str:
        if "работа в компании" in title_content.lower():
            return normalize_whitespace(title_content.rsplit("работа в компании", 1)[-1])
        return "Unknown company"

    @staticmethod
    def _extract_city(title_content: str) -> str | None:
        match = re.search(r"в ([A-ЯA-Za-zЁё\- ]+) с зарплатой", title_content)
        return normalize_whitespace(match.group(1)) if match else None

    @staticmethod
    def _extract_salary(title_content: str) -> tuple[Decimal | None, Decimal | None]:
        numbers = re.findall(r"(\d[\d ]*)\s*руб", title_content)
        if not numbers:
            return None, None
        parsed = [Decimal(number.replace(" ", "")) for number in numbers]
        if len(parsed) == 1:
            return parsed[0], None
        return parsed[0], parsed[1]
