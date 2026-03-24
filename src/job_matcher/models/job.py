from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_matcher.db.base import Base
from job_matcher.models.enums import EmploymentType, ExperienceLevel, JobStatus, RemoteMode
from job_matcher.models.mixins import TimestampMixin


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "external_id"),
        Index("ix_jobs_canonical_url", "canonical_url"),
        Index("ix_jobs_fingerprint", "fingerprint"),
        Index("ix_jobs_status_score", "status", "score"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_name: Mapped[str] = mapped_column(String(500), nullable=False)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(255), nullable=True)
    remote_mode: Mapped[str] = mapped_column(String(32), default=RemoteMode.UNKNOWN.value)
    employment_type: Mapped[str] = mapped_column(
        String(32), default=EmploymentType.UNKNOWN.value
    )
    experience_level: Mapped[str] = mapped_column(
        String(32), default=ExperienceLevel.UNKNOWN.value
    )
    salary_from: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_to: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String(16), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    description_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tech_tags_extracted: Mapped[list[str]] = mapped_column(JSON, default=list)
    search_query: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="ru")
    score: Mapped[int | None] = mapped_column(nullable=True)
    score_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    score_details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.NEW.value)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    duplicate_of: Mapped[Job | None] = relationship(remote_side=[id])
    snapshots: Mapped[list[JobSnapshot]] = relationship(back_populates="job")
    notifications: Mapped[list[Notification]] = relationship(back_populates="job")
    application_statuses: Mapped[list[ApplicationStatus]] = relationship(back_populates="job")
    user_feedback: Mapped[list[UserFeedback]] = relationship(back_populates="job")


class JobSnapshot(Base, TimestampMixin):
    __tablename__ = "job_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    job: Mapped[Job] = relationship(back_populates="snapshots")


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="telegram")
    recipient: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="notifications")


class ApplicationStatus(Base, TimestampMixin):
    __tablename__ = "application_statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="api")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="application_statuses")


class UserFeedback(Base, TimestampMixin):
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    job: Mapped[Job] = relationship(back_populates="user_feedback")
