"""Initial schema — all tables

Revision ID: 0001_initial
Revises: 
Create Date: 2024-03-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sources ──────────────────────────────────────────────────────────────
    op.create_table(
        "sources",
        sa.Column("id",          sa.Integer(),     primary_key=True),
        sa.Column("name",        sa.String(255),   nullable=False, unique=True),
        sa.Column("type",        sa.String(50),    nullable=False),
        sa.Column("base_url",    sa.String(2048)),
        sa.Column("is_active",   sa.Boolean(),     nullable=False, server_default="true"),
        sa.Column("config_json", sa.JSON()),
        sa.Column("created_at",  sa.DateTime(),    nullable=False, server_default=sa.func.now()),
    )

    # ── raw_reports ───────────────────────────────────────────────────────────
    op.create_table(
        "raw_reports",
        sa.Column("id",            sa.Integer(),  primary_key=True),
        sa.Column("source_id",     sa.Integer(),  sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("external_id",   sa.String(512)),
        sa.Column("source_url",    sa.String(2048)),
        sa.Column("raw_text",      sa.Text(),     nullable=False),
        sa.Column("raw_timestamp", sa.DateTime()),
        sa.Column("collected_at",  sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("media_json",    sa.JSON()),
        sa.Column("language",      sa.String(10)),
        sa.Column("content_hash",  sa.String(64), nullable=False),
        sa.Column("is_parsed",     sa.Boolean(),  nullable=False, server_default="false"),
        sa.Column("created_at",    sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_raw_report_source_hash"),
    )
    op.create_index("ix_raw_reports_content_hash",  "raw_reports", ["content_hash"])
    op.create_index("ix_raw_reports_raw_timestamp", "raw_reports", ["raw_timestamp"])
    op.create_index("ix_raw_reports_source_id",     "raw_reports", ["source_id"])
    op.create_index("ix_raw_reports_is_parsed",     "raw_reports", ["is_parsed"])
    op.create_index("ix_raw_reports_collected_at",  "raw_reports", ["collected_at"])

    # ── events ────────────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id",                   sa.Integer(),  primary_key=True),
        sa.Column("canonical_title",      sa.String(512)),
        sa.Column("summary",              sa.Text()),
        sa.Column("event_type",           sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("injured_count",        sa.Integer()),
        sa.Column("killed_count",         sa.Integer()),
        sa.Column("affected_people_text", sa.Text()),
        sa.Column("event_time",           sa.DateTime()),
        sa.Column("reported_time",        sa.DateTime()),
        sa.Column("location_text",        sa.String(512)),
        sa.Column("latitude",             sa.Float()),
        sa.Column("longitude",            sa.Float()),
        sa.Column("geocode_confidence",   sa.Float()),
        sa.Column("geocode_query",        sa.String(512)),
        sa.Column("parser_confidence",    sa.Float()),
        sa.Column("status",               sa.String(50), nullable=False, server_default="new"),
        sa.Column("first_seen_at",        sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at",         sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at",           sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",           sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_events_event_time",    "events", ["event_time"])
    op.create_index("ix_events_location_text", "events", ["location_text"])
    op.create_index("ix_events_event_type",    "events", ["event_type"])
    op.create_index("ix_events_status",        "events", ["status"])
    op.create_index("ix_events_lat_lng",       "events", ["latitude", "longitude"])
    op.create_index("ix_events_last_seen_at",  "events", ["last_seen_at"])

    # ── event_reports ─────────────────────────────────────────────────────────
    op.create_table(
        "event_reports",
        sa.Column("id",            sa.Integer(), primary_key=True),
        sa.Column("event_id",      sa.Integer(), sa.ForeignKey("events.id"),      nullable=False),
        sa.Column("raw_report_id", sa.Integer(), sa.ForeignKey("raw_reports.id"), nullable=False),
        sa.Column("relation_type", sa.String(50), nullable=False, server_default="primary"),
        sa.Column("dedup_score",   sa.Float()),
        sa.Column("dedup_reason",  sa.Text()),
        sa.Column("created_at",    sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_event_reports_event_id",      "event_reports", ["event_id"])
    op.create_index("ix_event_reports_raw_report_id", "event_reports", ["raw_report_id"])

    # ── event_media ───────────────────────────────────────────────────────────
    op.create_table(
        "event_media",
        sa.Column("id",            sa.Integer(),    primary_key=True),
        sa.Column("event_id",      sa.Integer(),    sa.ForeignKey("events.id"), nullable=False),
        sa.Column("media_type",    sa.String(50),   nullable=False, server_default="unknown"),
        sa.Column("media_url",     sa.String(2048), nullable=False),
        sa.Column("thumbnail_url", sa.String(2048)),
        sa.Column("source_url",    sa.String(2048)),
        sa.Column("caption",       sa.Text()),
        sa.Column("created_at",    sa.DateTime(),   nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_event_media_event_id", "event_media", ["event_id"])

    # ── event_updates ─────────────────────────────────────────────────────────
    op.create_table(
        "event_updates",
        sa.Column("id",               sa.Integer(),  primary_key=True),
        sa.Column("event_id",         sa.Integer(),  sa.ForeignKey("events.id"),      nullable=False),
        sa.Column("field_name",       sa.String(100), nullable=False),
        sa.Column("old_value",        sa.Text()),
        sa.Column("new_value",        sa.Text()),
        sa.Column("source_report_id", sa.Integer(),  sa.ForeignKey("raw_reports.id")),
        sa.Column("created_at",       sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_event_updates_event_id", "event_updates", ["event_id"])


def downgrade() -> None:
    op.drop_table("event_updates")
    op.drop_table("event_media")
    op.drop_table("event_reports")
    op.drop_table("events")
    op.drop_table("raw_reports")
    op.drop_table("sources")
