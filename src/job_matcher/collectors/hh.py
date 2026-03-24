from __future__ import annotations

from decimal import Decimal
from typing import Any

from job_matcher.collectors.base import BaseCollector
from job_matcher.core.config import Settings
from job_matcher.core.http import ResilientHttpClient
from job_matcher.models.enums import EmploymentType
from job_matcher.schemas.domain import CollectorResult, NormalizedJob
from job_matcher.utils.datetime import parse_datetime, utcnow
from job_matcher.utils.extraction import (
    detect_experience_level,
    detect_remote_mode,
    extract_tech_tags,
)
from job_matcher.utils.text import build_fingerprint, canonicalize_url, strip_html


class HHCollector(BaseCollector):
    source = "hh"

    def __init__(self, settings: Settings, http_client: ResilientHttpClient) -> None:
        self.settings = settings
        self.http_client = http_client

    async def collect(self, query: str) -> CollectorResult:
        payload = await self.http_client.get_json(
            f"{self.settings.hh_api_base_url}/vacancies",
            params={
                "text": query,
                "per_page": 20,
                "order_by": "publication_time",
                "area": 113,
            },
        )
        jobs = [self._to_job(item, query) for item in payload.get("items", [])]
        return CollectorResult(
            source=self.source,
            query=query,
            jobs=jobs,
            meta={"found": payload.get("found", 0), "pages": payload.get("pages", 0)},
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
