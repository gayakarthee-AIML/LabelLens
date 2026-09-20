from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Inspection, AuditLogEntry, User
from app.core.rbac import require_permission
from app.api.deps import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    all_inspections = db.query(Inspection).all()
    today = datetime.utcnow().date()

    total = len(all_inspections)
    today_count = sum(1 for i in all_inspections if i.created_at.date() == today)
    compliant = sum(1 for i in all_inspections if i.status == "COMPLIANT")
    non_compliant = sum(1 for i in all_inspections if i.status == "NON_COMPLIANT")
    review = sum(1 for i in all_inspections if i.status == "REVIEW_REQUIRED")
    violations = sum(
        1 for i in all_inspections for r in (i.rule_results or []) if r.get("status") == "FAIL"
    )
    pending_reviews = sum(1 for i in all_inspections if i.status == "REVIEW_REQUIRED")
    pending_sync = sum(1 for i in all_inspections if not i.synced)

    # Compliance trend — last 14 days.
    trend = []
    for offset in range(13, -1, -1):
        day = today - timedelta(days=offset)
        day_inspections = [i for i in all_inspections if i.created_at.date() == day]
        trend.append(
            {
                "date": day.isoformat(),
                "compliant": sum(1 for i in day_inspections if i.status == "COMPLIANT"),
                "nonCompliant": sum(1 for i in day_inspections if i.status == "NON_COMPLIANT"),
                "review": sum(1 for i in day_inspections if i.status == "REVIEW_REQUIRED"),
            }
        )

    category_counter: Counter = Counter()
    for i in all_inspections:
        if i.status == "NON_COMPLIANT":
            category_counter[i.category] += 1
    violations_by_category = [{"category": k, "count": v} for k, v in category_counter.most_common()]

    rule_counter: Counter = Counter()
    for i in all_inspections:
        for r in i.rule_results or []:
            if r.get("status") == "FAIL":
                rule_counter[r["rule"]["name"]] += 1
    common_violations = [{"rule": k, "count": v} for k, v in rule_counter.most_common(8)]

    return {
        "totalInspections": total,
        "todayInspections": today_count,
        "compliant": compliant,
        "nonCompliant": non_compliant,
        "reviewRequired": review,
        "violationsDetected": violations,
        "pendingReviews": pending_reviews,
        "pendingSync": pending_sync,
        "complianceTrend": trend,
        "violationsByCategory": violations_by_category,
        "commonViolations": common_violations,
    }


@router.get("/analytics")
def analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("VIEW_ANALYTICS")),
):
    """
    Deeper analytics than /summary: manual-review rate, barcode-mismatch
    rate, and the most common rule failures — all computed from real
    inspection/rule-result records, not sampled or estimated.
    """
    all_inspections = db.query(Inspection).all()
    total = len(all_inspections)

    review_count = sum(1 for i in all_inspections if i.status == "REVIEW_REQUIRED")
    manual_review_rate = (review_count / total) if total else 0.0

    scanned = [i for i in all_inspections if i.barcode_registry_match != "NOT_SCANNED"]
    mismatched = [i for i in scanned if i.barcode_registry_match == "MISMATCH"]
    barcode_mismatch_rate = (len(mismatched) / len(scanned)) if scanned else 0.0

    confidences = [
        d.get("confidence", 0)
        for i in all_inspections
        for d in (i.declarations or [])
        if d.get("status") == "PRESENT"
    ]
    average_ocr_confidence = (sum(confidences) / len(confidences)) if confidences else 0.0

    rule_counter: Counter = Counter()
    for i in all_inspections:
        for r in i.rule_results or []:
            if r.get("status") == "FAIL":
                rule_counter[r["rule"]["name"]] += 1
    common_violations = [{"rule": k, "count": v} for k, v in rule_counter.most_common(10)]

    category_counter: Counter = Counter()
    for i in all_inspections:
        category_counter[i.category] += 1
    inspections_by_category = [{"category": k, "count": v} for k, v in category_counter.most_common()]

    return {
        "totalInspections": total,
        "manualReviewRate": manual_review_rate,
        "barcodeMismatchRate": barcode_mismatch_rate,
        "averageOcrConfidence": average_ocr_confidence,
        "commonViolations": common_violations,
        "inspectionsByCategory": inspections_by_category,
    }


@router.get("/enforcement")
def enforcement_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("VIEW_ENFORCEMENT_DASHBOARD")),
):
    all_inspections = db.query(Inspection).all()

    severity_counter: Counter = Counter()
    for i in all_inspections:
        for r in i.rule_results or []:
            if r.get("status") == "FAIL":
                severity_counter[r["rule"]["severity"]] += 1

    manufacturer_counter: Counter = Counter()
    for i in all_inspections:
        if i.status == "NON_COMPLIANT":
            manufacturer_counter[i.brand] += 1

    unresolved = sum(
        1
        for i in all_inspections
        if i.status in ("NON_COMPLIANT", "REVIEW_REQUIRED")
        and not any(a.action == "FINALIZED" for a in i.audit_entries)
    )
    pending_reviews = sum(1 for i in all_inspections if i.status == "REVIEW_REQUIRED")

    return {
        "violationsBySeverity": [{"severity": k, "count": v} for k, v in severity_counter.most_common()],
        "repeatViolators": [
            {"manufacturer": k, "violationCount": v} for k, v in manufacturer_counter.most_common(10)
        ],
        "unresolvedFindings": unresolved,
        "pendingReviews": pending_reviews,
    }
