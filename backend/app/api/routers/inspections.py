from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Inspection, InspectionImage, ComplianceRuleORM, AuditLogEntry, User
from app.schemas.inspection import InspectionCreate, HumanVerificationRequest, EcommerceAnalyzeRequest
from app.api.deps import get_current_user
from app.core.rbac import require_permission
from app.services import cv_service, ocr_service, yolo_service, declaration_service, barcode_service, rule_engine
from app.services import storage_service, pdf_service, docx_service, event_bus, ecommerce_service, multimodal_service
from app.core.config import get_settings

router = APIRouter(prefix="/inspections", tags=["inspections"])
settings = get_settings()

REQUIRED_SLOTS = {"front", "back", "left", "right"}
# Barcode/QR capture is only required (and only scanned/cross-checked) for
# electronic products, per the brief — see Settings.is_electronic_category.


def _serialize(inspection: Inspection) -> dict:
    return {
        "id": inspection.id,
        "productName": inspection.product_name,
        "brand": inspection.brand,
        "category": inspection.category,
        "barcode": {
            "rawValue": inspection.barcode_raw_value,
            "symbology": inspection.barcode_symbology,
            "registryMatch": inspection.barcode_registry_match,
            "note": inspection.barcode_note,
        } if inspection.barcode_registry_match not in ("NOT_SCANNED",) or inspection.barcode_raw_value else None,
        "isElectronicCategory": settings.is_electronic_category(inspection.category),
        "sourceType": inspection.source_type,
        "sourceUrl": inspection.source_url,
        "ecommerceRawData": inspection.ecommerce_raw_data,
        "images": [
            {
                "slot": img.slot,
                "dataUrl": storage_service.presigned_url(img.storage_key),
                "capturedAt": img.captured_at.isoformat(),
                "qualityFlags": img.quality_flags,
                "uploaded": True,
                "remoteImageId": img.id,
                "note": img.note,
            }
            for img in inspection.images
        ],
        "declarations": [
            {
                "declarationType": d["declaration_type"],
                "detectedText": d.get("detected_text"),
                "confidence": d.get("confidence", 0),
                "boundingBox": d.get("bounding_box"),
                "sourceImage": d.get("source_image"),
                "status": d.get("status"),
                "applicableRule": d.get("applicable_rule", ""),
                "estimatedTextHeightPx": d.get("estimated_text_height_px"),
                "readability": d.get("readability"),
                "aiRationale": d.get("ai_rationale"),
            }
            for d in inspection.declarations
        ],
        "ruleResults": inspection.rule_results,
        "status": inspection.status,
        "inspectorId": inspection.inspector_id,
        "inspectorName": inspection.inspector_name,
        "inspectorRole": inspection.inspector_role,
        "location": inspection.location,
        "createdAt": inspection.created_at.isoformat(),
        "updatedAt": inspection.updated_at.isoformat(),
        "synced": inspection.synced,
        "notes": inspection.notes,
        "ruleVersion": inspection.rule_version,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def create_inspection(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("CREATE_INSPECTION")),
):
    inspection = Inspection(
        product_name=payload.productName,
        brand=payload.brand,
        category=payload.category,
        location=payload.location,
        inspector_id=current_user.id,
        inspector_name=current_user.full_name,
        inspector_role=current_user.role,
        status="DRAFT",
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    event_bus.publish("inspection.created", {"inspectionId": inspection.id})
    return _serialize(inspection)


@router.post("/{inspection_id}/images")
async def upload_image(
    inspection_id: str,
    slot: str = Form(...),
    capturedAt: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("CREATE_INSPECTION")),
):
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    raw_bytes = await file.read()

    # Real OpenCV pipeline: decode -> resize -> denoise -> contrast enhance ->
    # perspective correction, plus the quality report used for both inspector
    # feedback and the READABILITY rule evaluator later.
    processed_image, quality = cv_service.preprocess(raw_bytes)
    processed_bytes = cv_service.encode_jpeg(processed_image)

    original_key = storage_service.put_object(raw_bytes, prefix=f"inspections/{inspection_id}/original")
    processed_key = storage_service.put_object(processed_bytes, prefix=f"inspections/{inspection_id}/processed")

    image_row = InspectionImage(
        inspection_id=inspection_id,
        slot=slot,
        storage_key=original_key,
        processed_storage_key=processed_key,
        captured_at=datetime.fromisoformat(capturedAt.replace("Z", "+00:00")) if capturedAt else datetime.utcnow(),
        brightness=quality.brightness,
        blur_score=quality.blur_score,
        glare_pct=quality.glare_pct,
        quality_flags=quality.flags,
    )
    db.add(image_row)
    db.commit()
    db.refresh(image_row)

    return {"remoteImageId": image_row.id, "qualityFlags": quality.flags}


@router.post("/{inspection_id}/analyze")
def analyze(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("CREATE_INSPECTION")),
):
    """
    Runs the real pipeline: YOLO region detection -> PaddleOCR ->
    declaration extraction -> font/readability analysis -> barcode decode +
    registry cross-check -> rule engine evaluation. Persists and returns the
    fully populated inspection.
    """
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if not inspection.images:
        raise HTTPException(status_code=400, detail="No images uploaded yet — capture required angles first.")

    words_by_slot: dict[str, list[ocr_service.OcrWord]] = {}
    quality_by_slot: dict[str, dict] = {}
    decoded_barcode = None

    for img in inspection.images:
        image_bytes = storage_service.get_object(img.processed_storage_key or img.storage_key)
        image_array = cv_service.load_image(image_bytes)

        quality_by_slot[img.slot] = {
            "glare_pct": img.glare_pct or 0.0,
            "blur_score": img.blur_score or 100.0,
        }

        regions = yolo_service.detect_regions(image_array)
        slot_words: list[ocr_service.OcrWord] = []
        for region in regions:
            crop = image_array[region.y1:region.y2, region.x1:region.x2]
            if crop.size == 0:
                continue
            try:
                slot_words.extend(ocr_service.recognize(crop))
            except Exception:
                # PaddleOCR being unavailable/misconfigured (e.g. model
                # weights not downloaded yet) shouldn't crash the whole
                # analyze() call — degrades to "no words found for this
                # region" rather than a 500.
                pass
        words_by_slot[img.slot] = slot_words
        img.ocr_words = [
            {"text": w.text, "confidence": w.confidence, "box": w.box, "lang": w.lang} for w in slot_words
        ]

        if img.slot == "barcode" and settings.is_electronic_category(inspection.category):
            decoded_barcode = barcode_service.decode_barcode(image_array)

    db.commit()

    extracted = declaration_service.extract_declarations(words_by_slot, quality_by_slot)
    declarations_serialized = [
        {
            "declaration_type": d.declaration_type,
            "detected_text": d.detected_text,
            "confidence": d.confidence,
            "bounding_box": d.bounding_box,
            "source_image": d.source_image,
            "status": d.status,
            "estimated_text_height_px": d.estimated_text_height_px,
            "readability": d.readability,
        }
        for d in extracted
    ]

    # Cross-check against whatever manufacturer/net-quantity text was
    # actually extracted from this package's own declarations — not empty
    # placeholders. Without this, a registry entry could never be flagged as
    # mismatched even when the printed manufacturer clearly disagreed with it.
    declared_manufacturer = next(
        (d["detected_text"] for d in declarations_serialized if d["declaration_type"] == "MANUFACTURER_DETAILS"),
        "",
    ) or ""
    declared_net_quantity = next(
        (d["detected_text"] for d in declarations_serialized if d["declaration_type"] == "NET_QUANTITY"),
        None,
    )
    if settings.is_electronic_category(inspection.category):
        barcode_result = barcode_service.cross_check(
            db, decoded_barcode, inspection.brand, declared_manufacturer, declared_net_quantity
        )
    else:
        # Per the brief, QR/barcode scanning is only performed for
        # electronic products — for every other category this is a no-op,
        # not a missed scan, so it's reported as NOT_APPLICABLE rather than
        # NOT_SCANNED.
        barcode_result = {
            "rawValue": None,
            "symbology": None,
            "registryMatch": "NOT_APPLICABLE",
            "matchedProduct": None,
            "note": "Barcode/QR scanning applies only to electronic products for this category.",
        }
    inspection.barcode_raw_value = barcode_result["rawValue"]
    inspection.barcode_symbology = barcode_result["symbology"]
    inspection.barcode_registry_match = barcode_result["registryMatch"]
    inspection.barcode_note = barcode_result["note"]

    active_rules = db.query(ComplianceRuleORM).filter_by(enabled=True).all()
    eval_results = rule_engine.evaluate_all(
        active_rules, declarations_serialized, barcode_result, category=inspection.category
    )

    for d in declarations_serialized:
        matching_rule = next(
            (r.rule.rule_id for r in eval_results if r.rule.params.get("declaration_type") == d["declaration_type"]),
            "",
        )
        d["applicable_rule"] = matching_rule

    inspection.declarations = declarations_serialized
    inspection.rule_results = [
        {
            "rule": {
                "ruleId": r.rule.rule_id,
                "name": r.rule.name,
                "description": r.rule.description,
                "applicableCategory": r.rule.applicable_category,
                "requirement": r.rule.requirement,
                "validationType": r.rule.validation_type,
                "severity": r.rule.severity,
                "source": r.rule.source,
                "version": r.rule.version,
                "effectiveDate": r.rule.effective_date,
                "enabled": r.rule.enabled,
            },
            "status": r.status,
            "finding": r.finding,
            "evidence": r.evidence,
            "confidence": r.confidence,
            "recommendation": r.recommendation,
        }
        for r in eval_results
    ]
    inspection.status = rule_engine.overall_status(eval_results)
    inspection.rule_version = active_rules[0].version if active_rules else "unversioned"

    db.commit()
    db.refresh(inspection)
    event_bus.publish("inspection.analyzed", {"inspectionId": inspection.id, "status": inspection.status})
    return _serialize(inspection)


@router.post("/{inspection_id}/ecommerce/analyze")
def analyze_ecommerce_listing(
    inspection_id: str,
    payload: EcommerceAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("CREATE_INSPECTION")),
):
    """
    The E-Commerce Listing inspection mode. Pipeline (per the brief):

        URL -> webpage fetch -> HTML/JSON-LD/visible-text extraction ->
        product image extraction -> existing PaddleOCR pipeline on those
        images -> multimodal AI extraction for anything still missing ->
        structured declarations -> the SAME unmodified rule_engine.py used
        for physical inspections -> PASS/FAIL/NEEDS_VERIFICATION.

    The AI step (multimodal_service.py) only ever fills genuinely MISSING
    fields, and anything it finds is forced to AMBIGUOUS status below — so
    it can influence a REVIEW finding but can never resolve a rule straight
    to PASS by itself. The deterministic rule engine always makes the final
    call, exactly as for a physical inspection.
    """
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    try:
        html, used_headless_browser = ecommerce_service.fetch_listing_html_rendered(payload.url)
    except ecommerce_service.ListingFetchError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    listing = ecommerce_service.parse_listing(payload.url, html)
    listing.used_headless_browser = used_headless_browser

    # Product images: downloaded server-side (not captured by the
    # inspector's camera), then run through the SAME OpenCV preprocessing +
    # PaddleOCR pipeline used for physical label photos (cv_service.py,
    # ocr_service.py) — one image pipeline, two capture sources.
    image_words: dict[str, list[ocr_service.OcrWord]] = {}
    image_quality: dict[str, dict] = {}
    image_bytes_for_ai: list[bytes] = []

    for idx, image_url in enumerate(listing.image_urls):
        raw_bytes = ecommerce_service.download_image(image_url)
        if not raw_bytes:
            continue
        try:
            processed_image, quality = cv_service.preprocess(raw_bytes)
        except ValueError:
            continue
        processed_bytes = cv_service.encode_jpeg(processed_image)
        image_bytes_for_ai.append(processed_bytes)

        slot = f"ecommerce_image_{idx + 1}"
        original_key = storage_service.put_object(raw_bytes, prefix=f"inspections/{inspection_id}/original")
        processed_key = storage_service.put_object(processed_bytes, prefix=f"inspections/{inspection_id}/processed")
        image_row = InspectionImage(
            inspection_id=inspection_id,
            slot=slot,
            storage_key=original_key,
            processed_storage_key=processed_key,
            captured_at=datetime.utcnow(),
            brightness=quality.brightness,
            blur_score=quality.blur_score,
            glare_pct=quality.glare_pct,
            quality_flags=quality.flags,
            note=f"Downloaded from listing image: {image_url}",
        )
        db.add(image_row)
        db.flush()

        regions = yolo_service.detect_regions(processed_image)
        slot_words: list[ocr_service.OcrWord] = []
        for region in regions:
            crop = processed_image[region.y1:region.y2, region.x1:region.x2]
            if crop.size == 0:
                continue
            try:
                slot_words.extend(ocr_service.recognize(crop))
            except Exception:
                # Same graceful degradation as the physical-scan analyze()
                # endpoint — PaddleOCR being unavailable shouldn't crash the
                # whole listing analysis; the deterministic webpage-text
                # extraction and AI gap-filling still run regardless.
                pass
        image_words[slot] = slot_words
        image_quality[slot] = {"glare_pct": quality.glare_pct, "blur_score": quality.blur_score}
        image_row.ocr_words = [
            {"text": w.text, "confidence": w.confidence, "box": w.box, "lang": w.lang} for w in slot_words
        ]

    declarations = ecommerce_service.extract_declarations_from_listing(listing, image_words, image_quality)
    declarations_serialized = [
        {
            "declaration_type": d.declaration_type,
            "detected_text": d.detected_text,
            "confidence": d.confidence,
            "bounding_box": d.bounding_box,
            "source_image": d.source_image,
            "status": d.status,
            "estimated_text_height_px": d.estimated_text_height_px,
            "readability": d.readability,
        }
        for d in declarations
    ]

    # --- Multimodal AI extraction step — extraction ONLY, see module docstring ---
    missing_types = [d["declaration_type"] for d in declarations_serialized if d["status"] == "MISSING"]
    if missing_types and multimodal_service.enabled():
        ai_text = "\n".join(filter(None, [listing.title, listing.description, listing.visible_text[:3000]]))
        ai_fields = multimodal_service.extract_missing_fields(missing_types, ai_text, image_bytes_for_ai)
        by_type = {d["declaration_type"]: d for d in declarations_serialized}
        for field in ai_fields:
            decl = by_type.get(field.declaration_type)
            if not decl or decl["status"] != "MISSING":
                continue
            decl["detected_text"] = field.value
            decl["confidence"] = field.confidence
            decl["source_image"] = "ai_extraction"
            # Forced AMBIGUOUS regardless of the AI's own confidence — an
            # AI-only finding can trigger human REVIEW, never an automatic
            # PASS. This is the hard boundary the brief asks for.
            decl["status"] = "AMBIGUOUS"
            decl["ai_rationale"] = field.rationale
        declarations_serialized = list(by_type.values())

    declared_manufacturer = next(
        (d["detected_text"] for d in declarations_serialized if d["declaration_type"] == "MANUFACTURER_DETAILS"),
        "",
    ) or ""
    declared_net_quantity = next(
        (d["detected_text"] for d in declarations_serialized if d["declaration_type"] == "NET_QUANTITY"),
        None,
    )

    if settings.is_electronic_category(inspection.category) and listing.gtin:
        decoded = barcode_service.DecodedBarcode(raw_value=listing.gtin, symbology="EAN13")
        barcode_result = barcode_service.cross_check(
            db, decoded, inspection.brand, declared_manufacturer, declared_net_quantity
        )
    elif settings.is_electronic_category(inspection.category):
        barcode_result = {
            "rawValue": None,
            "symbology": None,
            "registryMatch": "NOT_SCANNED",
            "matchedProduct": None,
            "note": "No GTIN/barcode value was found in this listing's structured data.",
        }
    else:
        barcode_result = {
            "rawValue": None,
            "symbology": None,
            "registryMatch": "NOT_APPLICABLE",
            "matchedProduct": None,
            "note": "Barcode/QR scanning applies only to electronic products for this category.",
        }
    inspection.barcode_raw_value = barcode_result["rawValue"]
    inspection.barcode_symbology = barcode_result["symbology"]
    inspection.barcode_registry_match = barcode_result["registryMatch"]
    inspection.barcode_note = barcode_result["note"]

    # --- The unmodified, deterministic rule engine makes the final call ---
    active_rules = db.query(ComplianceRuleORM).filter_by(enabled=True).all()
    eval_results = rule_engine.evaluate_all(
        active_rules, declarations_serialized, barcode_result, category=inspection.category
    )
    for d in declarations_serialized:
        matching_rule = next(
            (r.rule.rule_id for r in eval_results if r.rule.params.get("declaration_type") == d["declaration_type"]),
            "",
        )
        d["applicable_rule"] = matching_rule

    inspection.declarations = declarations_serialized
    inspection.rule_results = [
        {
            "rule": {
                "ruleId": r.rule.rule_id,
                "name": r.rule.name,
                "description": r.rule.description,
                "applicableCategory": r.rule.applicable_category,
                "requirement": r.rule.requirement,
                "validationType": r.rule.validation_type,
                "severity": r.rule.severity,
                "source": r.rule.source,
                "version": r.rule.version,
                "effectiveDate": r.rule.effective_date,
                "enabled": r.rule.enabled,
            },
            "status": r.status,
            "finding": r.finding,
            "evidence": r.evidence,
            "confidence": r.confidence,
            "recommendation": r.recommendation,
        }
        for r in eval_results
    ]
    inspection.status = rule_engine.overall_status(eval_results)
    inspection.rule_version = active_rules[0].version if active_rules else "unversioned"
    inspection.source_type = "ECOMMERCE_LISTING"
    inspection.source_url = payload.url
    inspection.ecommerce_raw_data = {
        "title": listing.title,
        "description": listing.description[:2000],
        "price": listing.price,
        "currency": listing.currency,
        "brandFromListing": listing.brand,
        "gtin": listing.gtin,
        "imageUrls": listing.image_urls,
        "jsonLdProductsFound": len(listing.json_ld_products),
        "aiExtractionUsed": bool(missing_types and multimodal_service.enabled()),
        "usedHeadlessBrowser": listing.used_headless_browser,
    }

    db.add(
        AuditLogEntry(
            inspection_id=inspection.id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action="ECOMMERCE_LISTING_ANALYZED",
            detail={"url": payload.url, "status": inspection.status},
        )
    )
    db.commit()
    db.refresh(inspection)
    event_bus.publish("inspection.analyzed", {"inspectionId": inspection.id, "status": inspection.status})
    return _serialize(inspection)


@router.post("/{inspection_id}/verify")
def submit_human_verification(
    inspection_id: str,
    payload: HumanVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    if payload.declarationOverrides:
        by_type = {d["declaration_type"]: d for d in inspection.declarations}
        for override in payload.declarationOverrides:
            decl = by_type.get(override["declarationType"])
            if decl:
                decl["detected_text"] = override["detectedText"]
                decl["status"] = override["status"]
        inspection.declarations = list(by_type.values())
        db.add(
            AuditLogEntry(
                inspection_id=inspection.id,
                actor_id=current_user.id,
                actor_role=current_user.role,
                action="DECLARATION_EDITED",
                detail={"overrides": payload.declarationOverrides},
            )
        )

    if payload.ruleOverrides:
        by_id = {r["rule"]["ruleId"]: r for r in inspection.rule_results}
        for override in payload.ruleOverrides:
            r = by_id.get(override["ruleId"])
            if r:
                r["status"] = override["status"]
                r["finding"] = f"{r['finding']} (manually overridden: {override.get('note', '')})"
        inspection.rule_results = list(by_id.values())
        db.add(
            AuditLogEntry(
                inspection_id=inspection.id,
                actor_id=current_user.id,
                actor_role=current_user.role,
                action="RULE_OVERRIDDEN",
                detail={"overrides": payload.ruleOverrides},
            )
        )

    if payload.notes is not None:
        inspection.notes = payload.notes

    if payload.productName is not None and payload.productName.strip() and payload.productName != inspection.product_name:
        db.add(
            AuditLogEntry(
                inspection_id=inspection.id,
                actor_id=current_user.id,
                actor_role=current_user.role,
                action="PRODUCT_NAME_CONFIRMED",
                detail={"from": inspection.product_name, "to": payload.productName},
            )
        )
        inspection.product_name = payload.productName.strip()

    if payload.brand is not None and payload.brand.strip() and payload.brand != inspection.brand:
        db.add(
            AuditLogEntry(
                inspection_id=inspection.id,
                actor_id=current_user.id,
                actor_role=current_user.role,
                action="BRAND_CONFIRMED",
                detail={"from": inspection.brand, "to": payload.brand},
            )
        )
        inspection.brand = payload.brand.strip()

    db.commit()
    db.refresh(inspection)
    return _serialize(inspection)


@router.post("/{inspection_id}/finalize")
def finalize_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    db.add(
        AuditLogEntry(
            inspection_id=inspection.id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action="FINALIZED",
            detail={"status": inspection.status},
        )
    )
    db.commit()
    db.refresh(inspection)
    event_bus.publish("inspection.finalized", {"inspectionId": inspection.id, "status": inspection.status})
    return _serialize(inspection)


@router.get("/{inspection_id}")
def get_inspection(
    inspection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return _serialize(inspection)


@router.get("")
def search_inspections(
    query: str | None = Query(None),
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = Query(None),
    inspectorId: str | None = Query(None),
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Inspection)
    if query:
        like = f"%{query}%"
        q = q.filter(
            (Inspection.product_name.ilike(like))
            | (Inspection.brand.ilike(like))
            | (Inspection.barcode_raw_value.ilike(like))
            | (Inspection.inspector_name.ilike(like))
            | (Inspection.id.ilike(like))
        )
    if status_filter:
        q = q.filter(Inspection.status == status_filter)
    if category:
        q = q.filter(Inspection.category == category)
    if inspectorId:
        q = q.filter(Inspection.inspector_id == inspectorId)

    total = q.count()
    items = (
        q.order_by(Inspection.created_at.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )
    return {"items": [_serialize(i) for i in items], "total": total}


@router.get("/{inspection_id}/evidence")
def get_evidence(
    inspection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    Evidence viewer data: for every captured image, both the original and
    processed presigned URLs, the quality metrics measured on it, its raw
    OCR word list (text/confidence/bounding box), and which declarations/
    rule findings were sourced from it — everything section 26 of the brief
    asks the evidence viewer to show, in one call.
    """
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")

    declarations_by_slot: dict[str, list[dict]] = {}
    for d in inspection.declarations:
        declarations_by_slot.setdefault(d.get("source_image", ""), []).append(d)

    images_payload = []
    for img in inspection.images:
        images_payload.append(
            {
                "remoteImageId": img.id,
                "slot": img.slot,
                "originalUrl": storage_service.presigned_url(img.storage_key),
                "processedUrl": storage_service.presigned_url(img.processed_storage_key)
                if img.processed_storage_key
                else None,
                "capturedAt": img.captured_at.isoformat(),
                "quality": {
                    "brightness": img.brightness,
                    "blurScore": img.blur_score,
                    "glarePct": img.glare_pct,
                    "flags": img.quality_flags,
                },
                "ocrWords": img.ocr_words,
                "note": img.note,
                "relatedDeclarations": declarations_by_slot.get(img.slot, []),
            }
        )

    return {
        "inspectionId": inspection.id,
        "images": images_payload,
        "ruleResults": inspection.rule_results,
        "sourceType": inspection.source_type,
        "sourceUrl": inspection.source_url,
        "ecommerceRawData": inspection.ecommerce_raw_data,
        # Declarations sourced from the listing's own text (not an image) —
        # e.g. JSON-LD/page-text matches, or AI-extracted fields — have no
        # InspectionImage row to attach to above, so they're surfaced here
        # explicitly rather than silently dropped from the evidence view.
        "webpageDeclarations": declarations_by_slot.get("webpage", []) + declarations_by_slot.get("ai_extraction", []),
    }


@router.post("/{inspection_id}/images/{image_id}/note")
def add_evidence_note(
    inspection_id: str,
    image_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    image = db.get(InspectionImage, image_id)
    if not image or image.inspection_id != inspection_id:
        raise HTTPException(status_code=404, detail="Image not found on this inspection")
    note = (payload.get("note") or "").strip()
    image.note = note
    db.add(
        AuditLogEntry(
            inspection_id=inspection_id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action="EVIDENCE_NOTE_ADDED",
            detail={"imageId": image_id, "slot": image.slot, "note": note},
        )
    )
    db.commit()
    return {"remoteImageId": image.id, "note": image.note}


@router.post("/{inspection_id}/barcode/verify")
def reverify_barcode(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("CREATE_INSPECTION")),
):
    """
    Re-runs barcode decode + registry cross-check against the already-
    uploaded barcode-slot image, without re-running the full OCR/rule-engine
    pipeline. Useful after a retake of just the barcode image, or to check a
    barcode independently before committing to a full analysis pass.
    """
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    if not settings.is_electronic_category(inspection.category):
        raise HTTPException(
            status_code=400,
            detail="Barcode/QR scanning applies only to electronic products; this inspection's "
            f"category ('{inspection.category}') is not configured as electronic.",
        )

    barcode_image = next((img for img in inspection.images if img.slot == "barcode"), None)
    if not barcode_image:
        raise HTTPException(status_code=400, detail="No barcode image has been captured for this inspection yet.")

    image_bytes = storage_service.get_object(barcode_image.processed_storage_key or barcode_image.storage_key)
    image_array = cv_service.load_image(image_bytes)
    decoded = barcode_service.decode_barcode(image_array)

    declared_manufacturer = next(
        (d["detected_text"] for d in inspection.declarations if d["declaration_type"] == "MANUFACTURER_DETAILS"),
        "",
    ) or ""
    declared_net_quantity = next(
        (d["detected_text"] for d in inspection.declarations if d["declaration_type"] == "NET_QUANTITY"),
        None,
    )
    barcode_result = barcode_service.cross_check(
        db, decoded, inspection.brand, declared_manufacturer, declared_net_quantity
    )

    inspection.barcode_raw_value = barcode_result["rawValue"]
    inspection.barcode_symbology = barcode_result["symbology"]
    inspection.barcode_registry_match = barcode_result["registryMatch"]
    inspection.barcode_note = barcode_result["note"]
    db.add(
        AuditLogEntry(
            inspection_id=inspection.id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action="BARCODE_REVERIFIED",
            detail=barcode_result,
        )
    )
    db.commit()
    db.refresh(inspection)
    return {
        "rawValue": inspection.barcode_raw_value,
        "symbology": inspection.barcode_symbology,
        "registryMatch": inspection.barcode_registry_match,
        "note": inspection.barcode_note,
    }


@router.get("/reports/recent")
def recent_reports(
    limit: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("VIEW_ANALYTICS")),
):
    entries = (
        db.query(AuditLogEntry)
        .filter(AuditLogEntry.action == "REPORT_GENERATED")
        .order_by(AuditLogEntry.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for e in entries:
        inspection = db.get(Inspection, e.inspection_id)
        results.append(
            {
                "inspectionId": e.inspection_id,
                "productName": inspection.product_name if inspection else "(deleted inspection)",
                "format": e.detail.get("format"),
                "generatedBy": e.actor_role,
                "generatedAt": e.created_at.isoformat(),
            }
        )
    return results


@router.get("/{inspection_id}/report.pdf")
def get_pdf_report(
    inspection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    pdf_bytes = pdf_service.generate_pdf_report(inspection)
    db.add(
        AuditLogEntry(
            inspection_id=inspection.id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action="REPORT_GENERATED",
            detail={"format": "pdf"},
        )
    )
    db.commit()
    return Response(content=pdf_bytes, media_type="application/pdf")


@router.get("/{inspection_id}/report.docx")
def get_docx_report(
    inspection_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    inspection = db.get(Inspection, inspection_id)
    if not inspection:
        raise HTTPException(status_code=404, detail="Inspection not found")
    docx_bytes = docx_service.generate_docx_report(inspection)
    db.add(
        AuditLogEntry(
            inspection_id=inspection.id,
            actor_id=current_user.id,
            actor_role=current_user.role,
            action="REPORT_GENERATED",
            detail={"format": "docx"},
        )
    )
    db.commit()
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
