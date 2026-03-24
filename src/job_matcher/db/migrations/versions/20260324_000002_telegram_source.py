"""telegram source tables"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260324_000002"
down_revision = "20260324_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("query", sa.String(length=255), nullable=False),
        sa.Column("channel_username", sa.String(length=255), nullable=True),
        sa.Column("channel_title", sa.String(length=255), nullable=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=True),
        sa.Column("is_private", sa.Boolean(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_message_id", sa.BigInteger(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_channels")),
        sa.UniqueConstraint("query", name=op.f("uq_telegram_channels_query")),
        sa.UniqueConstraint("chat_id", name=op.f("uq_telegram_channels_chat_id")),
    )
    op.create_table(
        "telegram_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("channel_username", sa.String(length=255), nullable=True),
        sa.Column("channel_title", sa.String(length=255), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column("post_url", sa.Text(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("extracted_links", sa.JSON(), nullable=False),
        sa.Column("parsed_fields", sa.JSON(), nullable=False),
        sa.Column("is_vacancy", sa.Boolean(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["channel_id"], ["telegram_channels.id"], name=op.f("fk_telegram_messages_channel_id_telegram_channels")),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_telegram_messages_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_telegram_messages")),
        sa.UniqueConstraint("chat_id", "message_id", name=op.f("uq_telegram_messages_chat_id")),
    )
    op.create_index(op.f("ix_telegram_messages_channel_id"), "telegram_messages", ["channel_id"], unique=False)
    op.create_index(op.f("ix_telegram_messages_job_id"), "telegram_messages", ["job_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_telegram_messages_job_id"), table_name="telegram_messages")
    op.drop_index(op.f("ix_telegram_messages_channel_id"), table_name="telegram_messages")
    op.drop_table("telegram_messages")
    op.drop_table("telegram_channels")
