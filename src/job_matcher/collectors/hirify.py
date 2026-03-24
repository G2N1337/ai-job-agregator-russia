from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime

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
from job_matcher.utils.text import (
    build_fingerprint,
    canonicalize_url,
    normalize_whitespace,
    strip_html,
)


class HirifyCollector(BaseCollector):
    source = "hirify"

    def __init__(self, http_client: ResilientHttpClient) -> None:
        self.http_client = http_client

    async def collect(self, query: str) -> CollectorResult:
        xml_text = await self.http_client.get_text("https://hirify.me/sitemaps/jobs.xml")
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        root = ET.fromstring(xml_text)
        jobs: list[NormalizedJob] = []
        query_lower = query.lower()

        for item in root.findall("sm:url", namespace)[:250]:
            loc = item.findtext("sm:loc", namespaces=namespace)
            lastmod = item.findtext("sm:lastmod", namespaces=namespace)
            if not loc or query_lower not in loc.lower():
                continue
            detail_html = await self.http_client.get_text(loc)
            parsed = self._parse_detail(detail_html, loc, query, lastmod)
            if parsed is not None:
                jobs.append(parsed)
        return CollectorResult(source=self.source, query=query, jobs=jobs)

    def _parse_detail(
        self, html: str, url: str, query: str, lastmod: str | None
    ) -> NormalizedJob | None:
        soup = BeautifulSoup(html, "html.parser")
        title_value = soup.title.string if soup.title and soup.title.string else ""
        title = normalize_whitespace(title_value.replace("| Hirify", ""))
        page_text = soup.get_text(" ", strip=True)
        if query.lower() not in title.lower() and query.lower() not in page_text.lower():
            return None

        meta_description = soup.find("meta", attrs={"name": "description"})
        description_raw = str(meta_description.get("content", "")) if meta_description else ""
        description_text = normalize_whitespace(" ".join(soup.stripped_strings))
        company_name = "Company hidden"
        for candidate in soup.stripped_strings:
            if "Company hidden" in candidate:
                company_name = "Company hidden"
                break

        tags = extract_tech_tags([title, description_raw, description_text])
        published_at = None
        if lastmod:
            published_at = datetime.fromisoformat(lastmod)

        return NormalizedJob(
            source=self.source,
            external_id=url.rstrip("/").split("/")[-1].split("-")[0],
            source_url=url,
            canonical_url=canonicalize_url(url),
            title=title,
            company_name=company_name,
            city=None,
            country=self._extract_value(description_text, "Страна"),
            remote_mode=detect_remote_mode(title, description_raw, description_text),
            employment_type=EmploymentType.FULL_TIME,
            experience_level=detect_experience_level(title, description_text),
            salary_from=None,
            salary_to=None,
            salary_currency=None,
            published_at=published_at,
            collected_at=utcnow(),
            description_raw=description_raw,
            description_text=strip_html(description_text),
            tech_tags_extracted=tags,
            search_query=query,
            fingerprint=build_fingerprint(title, company_name, "", "", description_text),
            language="ru",
            raw_payload={"url": url, "lastmod": lastmod},
        )

    @staticmethod
    def _extract_value(text: str, label: str) -> str | None:
        lower = text.lower()
        marker = label.lower()
        if marker not in lower:
            return None
        start = lower.find(marker) + len(marker)
        tail = text[start:].strip(" :")
        return tail.split(" ", 1)[0] if tail else None
