"""Add font_size_standards table for the reference-card font-size feature.

Revision ID: 0002_font_size_standards
Revises: 0001_initial
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_font_size_standards"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "font_size_standards",
        sa.Column("standard_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("keyword", sa.String(), nullable=False, server_default=""),
        sa.Column("min_height_mm", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    op.drop_table("font_size_standards")
