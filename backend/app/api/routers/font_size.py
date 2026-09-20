"""
Font size checking endpoints.

Deliberately separate from /inspections/{id}/analyze — this is the
reference-card calibration workflow the brief asks for behind its own
button, not part of the declaration-extraction pipeline. See
app/services/font_size_service.py for the calibration + measurement logic.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import FontSizeStandardORM, User, AuditLogEntry, Inspection
from app.schemas.font_size import (
    FontSizeStandardOut,
    FontSizeStandardPatch,
    FontSizeStandardCreate,
    FontSizeCheckResult,
)
from app.api.deps import get_current_user
from app.core.rbac import require_permission
from app.services import cv_service, ocr_service, font_size_service

router = APIRouter(prefix="/font-size", tags=["font-size"])


def _standard_to_out(s: FontSizeStandardORM) -> FontSizeStandardOut:
    return FontSizeStandardOut(
        standardId=s.standard_id,
        name=s.name,
        keyword=s.keyword,
        minHeightMm=s.min_height_mm,
        source=s.source,
        version=s.version,
        enabled=s.enabled,
    )


@router.post("/check", response_model=FontSizeCheckResult)
async def check_font_size(
    file: UploadFile = File(...),
    cardWidthMm: float | None = Form(None),
    cardHeightMm: float | None = Form(None),
    inspectionId: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("CREATE_INSPECTION")),
):
    """
    Accepts ONE photo containing both a standard reference card (an ID-1
    card, e.g. a debit/credit card, by default) and the declaration text to
    be measured. Detects the card, derives a millimetres-per-pixel scale
    from its known physical size, OCRs the same image (English + Hindi),
    converts every detected text line's pixel height to millimetres, and
    compares each against the configurable minimum-height standards.
    """
    raw_bytes = await file.read()
    try:
        image = cv_service.load_image(raw_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    image = cv_service.resize_max_dim(image, max_dim=2400)

    card = font_size_service.detect_reference_card(image, cardWidthMm, cardHeightMm)
    if not card.found or not card.px_per_mm:
        return FontSizeCheckResult(
            card={"found": False, "pxPerMm": None, "confidence": card.confidence, "message": card.message},
            measurements=[],
            overallStatus="NEEDS_CARD",
        )

    words = ocr_service.recognize(image)
    measurements = font_size_service.measure_text_heights(words, card.px_per_mm)

    standards_rows = (
        db.query(FontSizeStandardORM).filter_by(enabled=True).all()
    )
    standards = [
        {
            "keyword": s.keyword,
            "min_height_mm": s.min_height_mm,
            "name": s.name,
            "source": s.source,
        }
        for s in standards_rows
    ]
    evaluated = font_size_service.evaluate_against_standards(measurements, standards)

    if any(e["status"] == "FAIL" for e in evaluated):
        overall = "FAIL"
    elif any(e["status"] == "REVIEW" for e in evaluated):
        overall = "REVIEW"
    elif evaluated:
        overall = "PASS"
    else:
        overall = "REVIEW"

    if inspectionId:
        inspection = db.get(Inspection, inspectionId)
        if inspection:
            db.add(
                AuditLogEntry(
                    inspection_id=inspectionId,
                    actor_id=current_user.id,
                    actor_role=current_user.role,
                    action="FONT_SIZE_CHECKED",
                    detail={"overallStatus": overall, "measurementCount": len(evaluated)},
                )
            )
            db.commit()

    return FontSizeCheckResult(
        card={
            "found": card.found,
            "pxPerMm": card.px_per_mm,
            "confidence": card.confidence,
            "message": card.message,
        },
        measurements=evaluated,
        overallStatus=overall,
    )


@router.get("/standards", response_model=list[FontSizeStandardOut])
def list_standards(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return [_standard_to_out(s) for s in db.query(FontSizeStandardORM).all()]


@router.post("/standards", response_model=FontSizeStandardOut)
def create_standard(
    payload: FontSizeStandardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_RULES")),
):
    if db.get(FontSizeStandardORM, payload.standardId):
        raise HTTPException(status_code=409, detail="A standard with this standardId already exists.")
    standard = FontSizeStandardORM(
        standard_id=payload.standardId,
        name=payload.name,
        keyword=payload.keyword,
        min_height_mm=payload.minHeightMm,
        source=payload.source,
        version="admin-authored",
        enabled=payload.enabled,
    )
    db.add(standard)
    db.commit()
    db.refresh(standard)
    return _standard_to_out(standard)


@router.patch("/standards/{standard_id}", response_model=FontSizeStandardOut)
def update_standard(
    standard_id: str,
    payload: FontSizeStandardPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_RULES")),
):
    standard = db.get(FontSizeStandardORM, standard_id)
    if not standard:
        raise HTTPException(status_code=404, detail="Standard not found")
    field_map = {"minHeightMm": "min_height_mm"}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(standard, field_map.get(field, field), value)
    db.commit()
    db.refresh(standard)
    return _standard_to_out(standard)
