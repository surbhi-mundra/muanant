"""baseline — projects, users, documents, audit_events

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-09
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # projects
    op.create_table(
        "projects",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_projects_slug", "projects", ["slug"])

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # documents
    op.create_table(
        "documents",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("project_id", sa.String(26), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_project_id", "documents", ["project_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_index("ix_documents_sha256", "documents", ["sha256"])

    # audit_events — append-only, hash-chained
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(26), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False, unique=True),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash", sa.String(64), nullable=False, unique=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("user_id", sa.String(26), nullable=True),
        sa.Column("project_id", sa.String(26), nullable=True),
        sa.Column("request_id", sa.String(64), nullable=True),
        sa.Column("workflow_id", sa.String(64), nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_audit_sequence", "audit_events", ["sequence"])
    op.create_index("ix_audit_category_ts", "audit_events", ["category", "timestamp"])
    op.create_index("ix_audit_project_ts", "audit_events", ["project_id", "timestamp"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])
    op.create_index("ix_audit_events_workflow_id", "audit_events", ["workflow_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_workflow_id", table_name="audit_events")
    op.drop_index("ix_audit_events_request_id", table_name="audit_events")
    op.drop_index("ix_audit_project_ts", table_name="audit_events")
    op.drop_index("ix_audit_category_ts", table_name="audit_events")
    op.drop_index("ix_audit_sequence", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index("ix_documents_sha256", table_name="documents")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_project_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_table("projects")
