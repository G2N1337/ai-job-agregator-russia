"""initial schema"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260324_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("company_name", sa.String(length=500), nullable=False),
        sa.Column("city", sa.String(length=255), nullable=True),
        sa.Column("country", sa.String(length=255), nullable=True),
        sa.Column("remote_mode", sa.String(length=32), nullable=False),
        sa.Column("employment_type", sa.String(length=32), nullable=False),
        sa.Column("experience_level", sa.String(length=32), nullable=False),
        sa.Column("salary_from", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_to", sa.Numeric(12, 2), nullable=True),
        sa.Column("salary_currency", sa.String(length=16), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("description_raw", sa.Text(), nullable=True),
        sa.Column("description_text", sa.Text(), nullable=True),
        sa.Column("tech_tags_extracted", sa.JSON(), nullable=False),
        sa.Column("search_query", sa.String(length=255), nullable=True),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=False),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("score_reasons", sa.JSON(), nullable=False),
        sa.Column("score_details", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("duplicate_of_id", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["duplicate_of_id"], ["jobs.id"], name=op.f("fk_jobs_duplicate_of_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("source", "external_id", name=op.f("uq_jobs_source")),
    )
    op.create_index("ix_jobs_canonical_url", "jobs", ["canonical_url"], unique=False)
    op.create_index("ix_jobs_fingerprint", "jobs", ["fingerprint"], unique=False)
    op.create_index("ix_jobs_status_score", "jobs", ["status", "score"], unique=False)

    op.create_table(
        "search_queries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("query", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_search_queries")),
        sa.UniqueConstraint("source", "query", name=op.f("uq_search_queries_source")),
    )

    op.create_table(
        "source_checkpoints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("query", sa.String(length=255), nullable=False),
        sa.Column("cursor", sa.String(length=255), nullable=True),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_checkpoints")),
        sa.UniqueConstraint("source", "query", name=op.f("uq_source_checkpoints_source")),
    )

    op.create_table(
        "scoring_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("rules_yaml", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scoring_profiles")),
        sa.UniqueConstraint("name", name=op.f("uq_scoring_profiles_name")),
    )

    op.create_table(
        "source_errors",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("query", sa.String(length=255), nullable=True),
        sa.Column("error_type", sa.String(length=100), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_errors")),
    )

    op.create_table(
        "job_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_snapshots_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_snapshots")),
    )
    op.create_index(op.f("ix_job_snapshots_job_id"), "job_snapshots", ["job_id"], unique=False)

    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=True),
        sa.Column("message_id", sa.String(length=255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_notifications_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
    )
    op.create_index(op.f("ix_notifications_job_id"), "notifications", ["job_id"], unique=False)

    op.create_table(
        "application_statuses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_application_statuses_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_statuses")),
    )
    op.create_index(op.f("ix_application_statuses_job_id"), "application_statuses", ["job_id"], unique=False)

    op.create_table(
        "user_feedback",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("feedback_type", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_user_feedback_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_feedback")),
    )
    op.create_index(op.f("ix_user_feedback_job_id"), "user_feedback", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_feedback_job_id"), table_name="user_feedback")
    op.drop_table("user_feedback")
    op.drop_index(op.f("ix_application_statuses_job_id"), table_name="application_statuses")
    op.drop_table("application_statuses")
    op.drop_index(op.f("ix_notifications_job_id"), table_name="notifications")
    op.drop_table("notifications")
    op.drop_index(op.f("ix_job_snapshots_job_id"), table_name="job_snapshots")
    op.drop_table("job_snapshots")
    op.drop_table("source_errors")
    op.drop_table("scoring_profiles")
    op.drop_table("source_checkpoints")
    op.drop_table("search_queries")
    op.drop_index("ix_jobs_status_score", table_name="jobs")
    op.drop_index("ix_jobs_fingerprint", table_name="jobs")
    op.drop_index("ix_jobs_canonical_url", table_name="jobs")
    op.drop_table("jobs")
