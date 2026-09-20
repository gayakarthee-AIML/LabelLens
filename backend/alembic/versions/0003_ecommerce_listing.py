"""Add e-commerce listing fields to inspections (source_type, source_url,
ecommerce_raw_data) for the E-Commerce Listing inspection mode.

Revision ID: 0003_ecommerce_listing
Revises: 0002_font_size_standards
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_ecommerce_listing"
down_revision = "0002_font_size_standards"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "inspections",
        sa.Column("source_type", sa.String(), nullable=False, server_default="PHYSICAL_INSPECTION"),
    )
    op.add_column("inspections", sa.Column("source_url", sa.String(), nullable=True))
    op.add_column("inspections", sa.Column("ecommerce_raw_data", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("inspections", "ecommerce_raw_data")
    op.drop_column("inspections", "source_url")
    op.drop_column("inspections", "source_type")
