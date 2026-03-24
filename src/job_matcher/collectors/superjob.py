from __future__ import annotations

from decimal import Decimal
from typing import Any

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
from job_matcher.utils.text import build_fingerprint, canonicalize_url, strip_html


class SuperJobCollector(BaseCollector):
    source = "superjob"

    def __init__(self, http_client: ResilientHttpClient, api_key: str | None) -> None:
        self.http_client = http_client
        self.api_key = api_key or ""

    async def collect(self, query: str) -> CollectorResult:
        if not self.api_key:
            return CollectorResult(
                source=self.source,
                query=query,
                jobs=[],
                meta={"status": "skipped", "reason": "SUPERJOB_API_KEY not configured"},
            )

        payload = await self.http_client._request(
            "GET",
            "https://api.superjob.ru/2.0/vacancies/",
            params={"keyword": query, "count": 20},
            headers={"X-Api-App-Id": self.api_key},
        )
        body: dict[str, Any] = payload.json()
        jobs = [self._to_job(item, query) for item in body.get("objects", [])]
        return CollectorResult(source=self.source, query=query, jobs=jobs, meta={"more": body.get("more")})

    def _to_job(self, item: dict[str, Any], query: str) -> NormalizedJob:
        description = strip_html(item.get("candidat", ""))
        payment_from = item.get("payment_from")
        payment_to = item.get("payment_to")
        return NormalizedJob(
            source=self.source,
            external_id=str(item["id"]),
            source_url=str(item.get("link") or ""),
            canonical_url=canonicalize_url(str(item.get("link") or "")),
            title=item.get("profession", "Unknown role"),
            company_name=item.get("firm_name", "Unknown company"),
            city=item.get("town", {}).get("title"),
            country="Russia",
            remote_mode=detect_remote_mode(item.get("profession"), description),
            employment_type=EmploymentType.FULL_TIME,
            experience_level=detect_experience_level(item.get("profession"), description),
            salary_from=Decimal(str(payment_from)) if payment_from else None,
            salary_to=Decimal(str(payment_to)) if payment_to else None,
            salary_currency="RUB",
            published_at=utcnow(),
            collected_at=utcnow(),
            description_raw=item.get("candidat"),
            description_text=description,
            tech_tags_extracted=extract_tech_tags([item.get("profession"), description]),
            search_query=query,
            fingerprint=build_fingerprint(
                item.get("profession", ""),
                item.get("firm_name", ""),
                str(payment_from or ""),
                str(payment_to or ""),
                description,
            ),
            language="ru",
            raw_payload=item,
        )
