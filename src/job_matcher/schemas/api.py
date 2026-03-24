from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


class JobResponse(BaseModel):
    id: int
    source: str
    external_id: str
    source_url: str
    canonical_url: str | None
    title: str
    company_name: str
    city: str | None
    country: str | None
    remote_mode: str
    employment_type: str
    experience_level: str
    salary_from: Decimal | None
    salary_to: Decimal | None
    salary_currency: str | None
    published_at: datetime | None
    collected_at: datetime
    first_seen_at: datetime
    last_seen_at: datetime
    description_text: str | None
    search_query: str | None
    tech_tags_extracted: list[str]
    score: int | None
    score_reasons: list[str]
    score_details: dict[str, Any]
    status: str
    duplicate_of_id: int | None
    language: str

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int


class StatsResponse(BaseModel):
    total_jobs: int
    new_jobs: int
    top_matches: int
    duplicates: int
    notifications_sent: int
    source_counts: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    database: str
    redis: str
    scheduler: str


class RunCollectionResponse(BaseModel):
    started: bool
    source: str | None = None
    message: str


class RescoreResponse(BaseModel):
    rescored: int


class SearchQueryResponse(BaseModel):
    id: int
    source: str
    query: str
    enabled: bool
    priority: int

    model_config = {"from_attributes": True}


class UpdateScoringProfileRequest(BaseModel):
    name: str = "custom"
    rules_yaml: str
    activate: bool = True


class StatusUpdateRequest(BaseModel):
    status: str
    note: str | None = None
    source: str = "api"
