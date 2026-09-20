import uuid
from datetime import datetime

from sqlalchemy import (
    String,
    Boolean,
    Float,
    Integer,
    ForeignKey,
    DateTime,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    official_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[str] = mapped_column(String)  # INSPECTOR | SENIOR_INSPECTOR | ADMINISTRATOR | REGULATOR
    jurisdiction: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ComplianceRuleORM(Base):
    __tablename__ = "compliance_rules"

    rule_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text)
    applicable_category: Mapped[str] = mapped_column(String)
    requirement: Mapped[str] = mapped_column(Text)
    validation_type: Mapped[str] = mapped_column(String)
    severity: Mapped[str] = mapped_column(String)
    source: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    effective_date: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Free-form JSON for validation-type-specific parameters, e.g. regex
    # patterns, numeric ranges, minimum font-size thresholds.
    params: Mapped[dict] = mapped_column(JSON, default=dict)


class FontSizeStandardORM(Base):
    """
    Configurable minimum text-height standards used by the font-size
    checking feature (see app/services/font_size_service.py). Seeded from
    app/rules/font_size_standards.yaml and editable by an Administrator
    through /api/v1/font-size/standards — the same dynamic-rule pattern used
    for ComplianceRuleORM, so font-size thresholds can be updated as Rule 8
    guidance changes without a code deployment.
    """

    __tablename__ = "font_size_standards"

    standard_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    # Substring (case-insensitive) matched against an OCR text line to decide
    # which standard applies to it, e.g. "mrp", "net". Empty/"DEFAULT" is the
    # fallback standard applied when no keyword matches.
    keyword: Mapped[str] = mapped_column(String, default="")
    min_height_mm: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String)
    version: Mapped[str] = mapped_column(String)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class RuleVersionHistory(Base):
    __tablename__ = "rule_version_history"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    version: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str] = mapped_column(String)
    change_summary: Mapped[str] = mapped_column(Text)


class ProductRegistryEntry(Base):
    __tablename__ = "product_registry"

    barcode: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    brand: Mapped[str] = mapped_column(String)
    manufacturer: Mapped[str] = mapped_column(String)
    declared_net_quantity: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    product_name: Mapped[str] = mapped_column(String)
    brand: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    location: Mapped[str | None] = mapped_column(String, nullable=True)

    status: Mapped[str] = mapped_column(String, default="DRAFT")
    rule_version: Mapped[str] = mapped_column(String, default="unversioned")
    notes: Mapped[str] = mapped_column(Text, default="")

    # Where this inspection's evidence came from. PHYSICAL_INSPECTION is the
    # original camera-capture flow; ECOMMERCE_LISTING is populated by
    # app/services/ecommerce_service.py from a product listing URL. Both
    # flows converge on the same declarations/rule_results shape so the
    # existing rule engine, evidence viewer, and PDF/DOCX reports work
    # unchanged regardless of source.
    source_type: Mapped[str] = mapped_column(String, default="PHYSICAL_INSPECTION")
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    # Snapshot of what was fetched/parsed from the listing (title, JSON-LD,
    # image URLs, truncated visible text) — kept for evidence/audit
    # transparency, not used by the rule engine itself.
    ecommerce_raw_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    barcode_raw_value: Mapped[str | None] = mapped_column(String, nullable=True)
    barcode_symbology: Mapped[str | None] = mapped_column(String, nullable=True)
    barcode_registry_match: Mapped[str] = mapped_column(String, default="NOT_SCANNED")
    barcode_note: Mapped[str] = mapped_column(Text, default="")

    # Declarations and rule results are stored as JSON blobs on the inspection
    # record for simplicity in this prototype; a production system would
    # normalize these into their own tables with foreign keys for querying.
    declarations: Mapped[list] = mapped_column(JSON, default=list)
    rule_results: Mapped[list] = mapped_column(JSON, default=list)

    inspector_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"))
    inspector_name: Mapped[str] = mapped_column(String)
    inspector_role: Mapped[str] = mapped_column(String)

    synced: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images: Mapped[list["InspectionImage"]] = relationship(back_populates="inspection", cascade="all, delete-orphan")
    audit_entries: Mapped[list["AuditLogEntry"]] = relationship(back_populates="inspection", cascade="all, delete-orphan")


class InspectionImage(Base):
    __tablename__ = "inspection_images"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    inspection_id: Mapped[str] = mapped_column(String, ForeignKey("inspections.id"))
    slot: Mapped[str] = mapped_column(String)  # front | back | left | right | barcode | top | bottom | additional
    storage_key: Mapped[str] = mapped_column(String)  # object key in MinIO/S3
    processed_storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    blur_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    glare_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality_flags: Mapped[list] = mapped_column(JSON, default=list)

    ocr_words: Mapped[list] = mapped_column(JSON, default=list)  # [{text, confidence, bbox, lang}]
    note: Mapped[str] = mapped_column(Text, default="")  # inspector annotation, evidence viewer

    inspection: Mapped["Inspection"] = relationship(back_populates="images")


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=gen_uuid)
    inspection_id: Mapped[str] = mapped_column(String, ForeignKey("inspections.id"))
    actor_id: Mapped[str] = mapped_column(String)
    actor_role: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)  # e.g. "DECLARATION_EDITED", "RULE_OVERRIDDEN", "FINALIZED"
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    inspection: Mapped["Inspection"] = relationship(back_populates="audit_entries")
