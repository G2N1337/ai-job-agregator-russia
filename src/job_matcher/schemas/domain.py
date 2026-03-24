from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from job_matcher.models.enums import EmploymentType, ExperienceLevel, JobStatus, RemoteMode


class NormalizedJob(BaseModel):
    source: str
    external_id: str
    source_url: str
    canonical_url: str | None = None
    title: str
    company_name: str
    city: str | None = None
    country: str | None = None
    remote_mode: RemoteMode = RemoteMode.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    experience_level: ExperienceLevel = ExperienceLevel.UNKNOWN
    salary_from: Decimal | None = None
    salary_to: Decimal | None = None
    salary_currency: str | None = None
    published_at: datetime | None = None
    collected_at: datetime
    description_raw: str | None = None
    description_text: str | None = None
    tech_tags_extracted: list[str] = Field(default_factory=list)
    search_query: str | None = None
    fingerprint: str
    language: str = "ru"
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ScoreResult(BaseModel):
    score: int
    reasons: list[str]
    details: dict[str, Any] = Field(default_factory=dict)


class CollectorResult(BaseModel):
    source: str
    query: str
    jobs: list[NormalizedJob]
    checkpoint_cursor: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)
    raw_items: list[dict[str, Any]] = Field(default_factory=list)


class JobUpdatePayload(BaseModel):
    status: JobStatus
    note: str | None = None
    source: str = "api"
