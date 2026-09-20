import json
import io
from datetime import datetime

import yaml
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import ComplianceRuleORM, RuleVersionHistory, User
from app.schemas.rule import RuleOut, RuleCreate, RulePatch, RuleToggle
from app.core.rbac import require_permission

router = APIRouter(prefix="/rules", tags=["rules"])


def _to_out(rule: ComplianceRuleORM) -> RuleOut:
    return RuleOut(
        ruleId=rule.rule_id,
        name=rule.name,
        description=rule.description,
        applicableCategory=rule.applicable_category,
        requirement=rule.requirement,
        validationType=rule.validation_type,
        severity=rule.severity,
        source=rule.source,
        version=rule.version,
        effectiveDate=rule.effective_date,
        enabled=rule.enabled,
    )


@router.get("", response_model=list[RuleOut])
def list_rules(
    category: str | None = None,
    enabled: bool | None = None,
    query: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_RULES")),
):
    q = db.query(ComplianceRuleORM)
    if category:
        q = q.filter(ComplianceRuleORM.applicable_category == category)
    if enabled is not None:
        q = q.filter(ComplianceRuleORM.enabled == enabled)
    if query:
        like = f"%{query}%"
        q = q.filter((ComplianceRuleORM.name.ilike(like)) | (ComplianceRuleORM.rule_id.ilike(like)))
    return [_to_out(r) for r in q.all()]


@router.post("", response_model=RuleOut)
def create_rule(
    payload: RuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_RULES")),
):
    if db.get(ComplianceRuleORM, payload.ruleId):
        raise HTTPException(status_code=409, detail="A rule with this ruleId already exists.")
    rule = ComplianceRuleORM(
        rule_id=payload.ruleId,
        name=payload.name,
        description=payload.description,
        applicable_category=payload.applicableCategory,
        requirement=payload.requirement,
        validation_type=payload.validationType,
        severity=payload.severity,
        source=payload.source,
        version="admin-authored",
        effective_date=payload.effectiveDate,
        enabled=payload.enabled,
        params=payload.params,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _to_out(rule)


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(
    rule_id: str,
    payload: RulePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_RULES")),
):
    rule = db.get(ComplianceRuleORM, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(rule, _camel_to_snake(field), value)
    db.commit()
    db.refresh(rule)
    return _to_out(rule)


def _camel_to_snake(name: str) -> str:
    mapping = {
        "effectiveDate": "effective_date",
    }
    return mapping.get(name, name)


@router.post("/{rule_id}/toggle", response_model=RuleOut)
def toggle_rule(
    rule_id: str,
    payload: RuleToggle,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_RULES")),
):
    rule = db.get(ComplianceRuleORM, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.enabled = payload.enabled
    db.commit()
    db.refresh(rule)
    return _to_out(rule)


@router.get("/export")
def export_rules(
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("MANAGE_RULES"))
):
    rules = db.query(ComplianceRuleORM).all()
    payload = {
        "exportedAt": datetime.utcnow().isoformat(),
        "rules": [
            {
                "rule_id": r.rule_id,
                "name": r.name,
                "description": r.description,
                "applicable_category": r.applicable_category,
                "requirement": r.requirement,
                "validation_type": r.validation_type,
                "severity": r.severity,
                "source": r.source,
                "version": r.version,
                "effective_date": r.effective_date,
                "enabled": r.enabled,
                "params": r.params,
            }
            for r in rules
        ],
    }
    return Response(content=json.dumps(payload, indent=2), media_type="application/json")


@router.post("/import")
async def import_rules(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("MANAGE_RULES")),
):
    raw = await file.read()
    if file.filename and file.filename.endswith((".yaml", ".yml")):
        data = yaml.safe_load(raw)
    else:
        data = json.loads(raw)

    rules = data.get("rules", [])
    imported = 0
    for r in rules:
        existing = db.get(ComplianceRuleORM, r["rule_id"])
        if existing:
            for field in ["name", "description", "requirement", "severity", "effective_date", "enabled", "params"]:
                if field in r:
                    setattr(existing, field, r[field])
        else:
            db.add(ComplianceRuleORM(**r, version=data.get("version", "imported")))
        imported += 1

    version = data.get("version", f"imported-{datetime.utcnow().isoformat()}")
    db.add(
        RuleVersionHistory(
            version=version,
            source=file.filename or "manual import",
            change_summary=f"Imported {imported} rule definitions.",
        )
    )
    db.commit()
    return {"imported": imported, "version": version}


@router.get("/history")
def rule_history(
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("MANAGE_RULES"))
):
    entries = db.query(RuleVersionHistory).order_by(RuleVersionHistory.published_at.desc()).all()
    return [
        {
            "version": e.version,
            "publishedAt": e.published_at.isoformat(),
            "source": e.source,
            "changeSummary": e.change_summary,
        }
        for e in entries
    ]
