"""Initial schema — users, compliance_rules, rule_version_history,
product_registry, inspections, inspection_images, audit_log.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("official_id", sa.String(), nullable=False, unique=True),
        sa.Column("full_name", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("jurisdiction", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_official_id", "users", ["official_id"], unique=True)

    op.create_table(
        "compliance_rules",
        sa.Column("rule_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("applicable_category", sa.String(), nullable=False),
        sa.Column("requirement", sa.Text(), nullable=False),
        sa.Column("validation_type", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("effective_date", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("params", sa.JSON(), nullable=False, server_default="{}"),
    )

    op.create_table(
        "rule_version_history",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
    )

    op.create_table(
        "product_registry",
        sa.Column("barcode", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=False),
        sa.Column("manufacturer", sa.String(), nullable=False),
        sa.Column("declared_net_quantity", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
    )

    op.create_table(
        "inspections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("brand", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="DRAFT"),
        sa.Column("rule_version", sa.String(), nullable=False, server_default="unversioned"),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("barcode_raw_value", sa.String(), nullable=True),
        sa.Column("barcode_symbology", sa.String(), nullable=True),
        sa.Column("barcode_registry_match", sa.String(), nullable=False, server_default="NOT_SCANNED"),
        sa.Column("barcode_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("declarations", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("rule_results", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("inspector_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("inspector_name", sa.String(), nullable=False),
        sa.Column("inspector_role", sa.String(), nullable=False),
        sa.Column("synced", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_inspections_status", "inspections", ["status"])
    op.create_index("ix_inspections_created_at", "inspections", ["created_at"])
    op.create_index("ix_inspections_barcode_raw_value", "inspections", ["barcode_raw_value"])

    op.create_table(
        "inspection_images",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("inspection_id", sa.String(), sa.ForeignKey("inspections.id"), nullable=False),
        sa.Column("slot", sa.String(), nullable=False),
        sa.Column("storage_key", sa.String(), nullable=False),
        sa.Column("processed_storage_key", sa.String(), nullable=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("brightness", sa.Float(), nullable=True),
        sa.Column("blur_score", sa.Float(), nullable=True),
        sa.Column("glare_pct", sa.Float(), nullable=True),
        sa.Column("quality_flags", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("ocr_words", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_inspection_images_inspection_id", "inspection_images", ["inspection_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("inspection_id", sa.String(), sa.ForeignKey("inspections.id"), nullable=False),
        sa.Column("actor_id", sa.String(), nullable=False),
        sa.Column("actor_role", sa.String(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_inspection_id", "audit_log", ["inspection_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade():
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_inspection_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_index("ix_inspection_images_inspection_id", table_name="inspection_images")
    op.drop_table("inspection_images")

    op.drop_index("ix_inspections_barcode_raw_value", table_name="inspections")
    op.drop_index("ix_inspections_created_at", table_name="inspections")
    op.drop_index("ix_inspections_status", table_name="inspections")
    op.drop_table("inspections")

    op.drop_table("product_registry")
    op.drop_table("rule_version_history")
    op.drop_table("compliance_rules")

    op.drop_index("ix_users_official_id", table_name="users")
    op.drop_table("users")
