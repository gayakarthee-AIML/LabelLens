"""
Configurable Legal Metrology rule engine.

Rules are never hardcoded in a frontend component or inline in this file —
they live in `app/rules/legal_metrology_rules.yaml` (seeded into the
`compliance_rules` DB table at startup, see app/db/seed.py) and are editable
through the Administrator Rule Management UI / `/api/v1/rules` endpoints.
This module only knows how to EVALUATE a rule against inspection data for a
given `validation_type` — it holds no product- or rule-specific literals.

`GovRuleFeedAdapter` is the "Government Rule Update Architecture" the brief
asks for: a real, callable interface with a clearly disabled default,
instead of a fabricated government API.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import ComplianceRuleORM, RuleVersionHistory

settings = get_settings()


@dataclass
class RuleEvalResult:
    rule: ComplianceRuleORM
    status: str  # PASS | FAIL | REVIEW
    finding: str
    evidence: str
    confidence: float
    recommendation: str


def _declaration_by_type(declarations: list[dict], declaration_type: str) -> dict | None:
    for d in declarations:
        if d["declaration_type"] == declaration_type:
            return d
    return None


def _eval_presence(rule: ComplianceRuleORM, declarations: list[dict]) -> RuleEvalResult:
    decl = _declaration_by_type(declarations, rule.params["declaration_type"])
    if decl is None or decl["status"] == "MISSING":
        return RuleEvalResult(
            rule, "FAIL",
            finding=f"{rule.params['declaration_type'].replace('_', ' ').title()} was not detected on any captured image.",
            evidence="No matching OCR text found across captured images.",
            confidence=0.7,
            recommendation="Confirm manually — the declaration may be present but not detected due to angle, glare, or damage.",
        )
    if decl["status"] == "AMBIGUOUS":
        return RuleEvalResult(
            rule, "REVIEW",
            finding=f"A possible {rule.params['declaration_type'].replace('_', ' ').title()} was detected but with low confidence.",
            evidence=f"Detected text: '{decl['detected_text']}' (confidence {decl['confidence']:.0%}).",
            confidence=decl["confidence"],
            recommendation="Manual verification recommended before recording a final finding.",
        )
    if decl.get("readability") == "POOR":
        # A declaration can match its regex cleanly (status PRESENT) while
        # the underlying image quality was bad enough that the OCR text
        # itself is unreliable — e.g. a low-confidence, glare/blur-affected
        # read that happened to still resemble the expected pattern. Status
        # PRESENT + readability POOR shown together is a contradiction: one
        # signal says "definitely here", the other says "might be garbled".
        # Downgrading to REVIEW here resolves that inconsistency in favor of
        # caution rather than silently reporting a shaky read as a clean PASS.
        return RuleEvalResult(
            rule, "REVIEW",
            finding=f"{rule.params['declaration_type'].replace('_', ' ').title()} was detected, but the source image quality was poor enough that the text may be misread.",
            evidence=f"Detected text: '{decl['detected_text']}' — flagged POOR readability (glare/blur/low OCR confidence).",
            confidence=min(decl["confidence"], 0.5),
            recommendation="Recapture this panel with better lighting/focus, or manually verify the printed text against the photo.",
        )
    return RuleEvalResult(
        rule, "PASS",
        finding=f"{rule.params['declaration_type'].replace('_', ' ').title()} detected.",
        evidence=f"Detected text: '{decl['detected_text']}' (confidence {decl['confidence']:.0%}).",
        confidence=decl["confidence"],
        recommendation="",
    )


def _eval_format(rule: ComplianceRuleORM, declarations: list[dict]) -> RuleEvalResult:
    decl = _declaration_by_type(declarations, rule.params["declaration_type"])
    if decl is None or decl["status"] == "MISSING" or not decl["detected_text"]:
        return RuleEvalResult(
            rule, "REVIEW",
            finding="Declaration not detected — format could not be checked.",
            evidence="No detected text to evaluate against the required pattern.",
            confidence=0.5,
            recommendation="Resolve the underlying presence finding first.",
        )
    pattern = rule.params.get("pattern")
    if pattern and re.search(pattern, decl["detected_text"]):
        return RuleEvalResult(
            rule, "PASS",
            finding="Declared value matches the required format.",
            evidence=f"'{decl['detected_text']}' matches pattern.",
            confidence=decl["confidence"],
            recommendation="",
        )
    return RuleEvalResult(
        rule, "FAIL",
        finding="Declared value does not match the required standard-unit format.",
        evidence=f"Detected text '{decl['detected_text']}' does not match the expected pattern.",
        confidence=decl["confidence"],
        recommendation="Verify the printed unit is a standard weight/volume unit (g, kg, ml, l).",
    )


# Declaration sources with no physical basis for a pixel-height/readability
# check — plain webpage text has no "printed size" at all, and an
# AI-extracted field has no bounding box either. FONT_SIZE and READABILITY
# only mean something for a declaration that was actually read off a
# photographed image (a physical package/label photo, or a downloaded
# product image from a listing). Excluding these here (rather than letting
# them fall through with a placeholder box height) is the fix for a real bug
# where webpage-sourced declarations were silently fabricating a PASS.
_NON_PHYSICAL_SOURCES = {"webpage", "ai_extraction"}


def _eval_font_size(rule: ComplianceRuleORM, declarations: list[dict]) -> RuleEvalResult:
    applies_to = rule.params.get("applies_to", [])
    threshold = rule.params.get("min_estimated_px", 14)
    failing = []
    reviewed = []
    not_applicable = []
    for decl_type in applies_to:
        decl = _declaration_by_type(declarations, decl_type)
        if decl is not None and decl.get("source_image") in _NON_PHYSICAL_SOURCES:
            not_applicable.append(decl_type)
            continue
        if decl is None or decl.get("estimated_text_height_px") is None:
            reviewed.append(decl_type)
            continue
        if decl["estimated_text_height_px"] < threshold:
            failing.append((decl_type, decl["estimated_text_height_px"]))

    na_note = f" (not applicable — sourced from listing text/AI, not a photographed image: {', '.join(not_applicable)})" if not_applicable else ""

    if failing:
        detail = ", ".join(f"{t} ({h:.1f}px)" for t, h in failing)
        return RuleEvalResult(
            rule, "FAIL",
            finding=f"Estimated text height below the {threshold}px threshold for: {detail}.{na_note}",
            evidence="Heights are OCR-bounding-box estimates in pixels, not a physical measurement — "
                     "physical measurement requires a calibrated/reference scale, not yet configured.",
            confidence=0.6,
            recommendation="Use a calibrated reference scale for a definitive physical measurement before citing this as a violation.",
        )
    if reviewed:
        return RuleEvalResult(
            rule, "REVIEW",
            finding=f"Could not estimate text height for: {', '.join(reviewed)}.{na_note}",
            evidence="Underlying declaration was not detected clearly enough to measure its bounding box.",
            confidence=0.4,
            recommendation="Recapture the relevant panel at a closer distance.",
        )
    return RuleEvalResult(
        rule, "PASS",
        finding=f"Estimated text heights meet the configured threshold for all checked declarations sourced from photographed images.{na_note}",
        evidence="Estimates are pixel-based; no physical calibration reference was used.",
        confidence=0.6,
        recommendation="",
    )


def _eval_readability(rule: ComplianceRuleORM, declarations: list[dict]) -> RuleEvalResult:
    # Only declarations sourced from an actual photographed image have a
    # meaningful readability signal (OCR confidence + glare/blur) — webpage
    # text and AI-extracted fields never went through image quality scoring
    # at all, so they're excluded here rather than silently carrying a
    # readability value that was never really computed for them.
    physical_declarations = [d for d in declarations if d.get("source_image") not in _NON_PHYSICAL_SOURCES]
    poor = [d["declaration_type"] for d in physical_declarations if d.get("readability") == "POOR"]
    review = [d["declaration_type"] for d in physical_declarations if d.get("readability") == "REVIEW"]
    if poor:
        return RuleEvalResult(
            rule, "FAIL",
            finding=f"Poor readability detected for: {', '.join(poor)}.",
            evidence="Low OCR confidence combined with glare/blur/brightness issues on the source image.",
            confidence=0.65,
            recommendation="Recapture the affected panel with better lighting and a steadier hand.",
        )
    if review:
        return RuleEvalResult(
            rule, "REVIEW",
            finding=f"Readability borderline for: {', '.join(review)}.",
            evidence="OCR confidence or image quality was in the uncertain range.",
            confidence=0.5,
            recommendation="Manual verification recommended.",
        )
    return RuleEvalResult(rule, "PASS", finding="No readability issues detected.", evidence="", confidence=0.8, recommendation="")


def _parse_numeric(text: str | None) -> float | None:
    if not text:
        return None
    match = re.search(r"[\d,]+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _eval_text_pattern(rule: ComplianceRuleORM, declarations: list[dict]) -> RuleEvalResult:
    """
    Generic regex check against a declaration's detected text. Distinct from
    FORMAT (which is specifically "does the value look like a standard
    unit"): TEXT_PATTERN is used for misleading/non-standard phrasing checks
    per brief section 16 — e.g. flagging ambiguous pricing language on the
    MRP declaration. `mode` is "must_match" or "must_not_match".
    """
    decl_type = rule.params.get("declaration_type")
    decl = _declaration_by_type(declarations, decl_type)
    if decl is None or decl["status"] == "MISSING" or not decl.get("detected_text"):
        return RuleEvalResult(
            rule, "REVIEW",
            finding="Declaration not detected — text pattern could not be checked.",
            evidence="No detected text available to evaluate.",
            confidence=0.5,
            recommendation="Resolve the underlying presence finding first.",
        )

    text = decl["detected_text"]
    pattern = rule.params.get("pattern", "")
    mode = rule.params.get("mode", "must_match")
    matched = bool(re.search(pattern, text, re.IGNORECASE)) if pattern else False

    passed = matched if mode == "must_match" else not matched
    if passed:
        return RuleEvalResult(
            rule, "PASS",
            finding="Declared text does not raise a pattern-based concern.",
            evidence=f"'{text}' evaluated against configured pattern ({mode}).",
            confidence=decl["confidence"],
            recommendation="",
        )
    return RuleEvalResult(
        rule, "REVIEW" if rule.severity in ("MINOR", "ADVISORY") else "FAIL",
        finding=f"Potential non-standard or misleading declaration text: '{text}'.",
        evidence=f"Text did not satisfy the configured pattern check ({mode}: {pattern}).",
        confidence=decl["confidence"],
        recommendation="Review wording manually before treating this as a confirmed violation — "
        "pattern checks flag candidates, they do not make a legal determination.",
    )


def _eval_numeric(rule: ComplianceRuleORM, declarations: list[dict]) -> RuleEvalResult:
    decl_type = rule.params.get("declaration_type")
    decl = _declaration_by_type(declarations, decl_type)
    if decl is None or decl["status"] == "MISSING":
        return RuleEvalResult(
            rule, "REVIEW",
            finding="Declaration not detected — numeric check could not run.",
            evidence="No detected text available to parse a numeric value from.",
            confidence=0.5,
            recommendation="Resolve the underlying presence finding first.",
        )
    value = _parse_numeric(decl.get("detected_text"))
    if value is None:
        return RuleEvalResult(
            rule, "REVIEW",
            finding=f"Could not parse a numeric value from '{decl.get('detected_text')}'.",
            evidence="OCR text did not contain a recognizable number.",
            confidence=decl["confidence"] * 0.6,
            recommendation="Recapture the panel — the value may be present but not legible enough to OCR.",
        )
    min_value = rule.params.get("min")
    if min_value is not None and value < min_value:
        return RuleEvalResult(
            rule, "FAIL",
            finding=f"Declared value {value} is below the minimum permitted value of {min_value}.",
            evidence=f"Detected text '{decl.get('detected_text')}' parsed as {value}.",
            confidence=decl["confidence"],
            recommendation="Verify the printed value directly — OCR misreads (e.g. missing a digit) are a common cause.",
        )
    return RuleEvalResult(
        rule, "PASS",
        finding=f"Declared value {value} satisfies the numeric requirement.",
        evidence=f"Detected text '{decl.get('detected_text')}' parsed as {value}.",
        confidence=decl["confidence"],
        recommendation="",
    )


def _eval_range(rule: ComplianceRuleORM, declarations: list[dict]) -> RuleEvalResult:
    decl_type = rule.params.get("declaration_type")
    decl = _declaration_by_type(declarations, decl_type)
    if decl is None or decl["status"] == "MISSING":
        return RuleEvalResult(
            rule, "REVIEW",
            finding="Declaration not detected — range check could not run.",
            evidence="No detected text available to parse a numeric value from.",
            confidence=0.5,
            recommendation="Resolve the underlying presence finding first.",
        )
    value = _parse_numeric(decl.get("detected_text"))
    if value is None:
        return RuleEvalResult(
            rule, "REVIEW",
            finding=f"Could not parse a numeric value from '{decl.get('detected_text')}' to range-check.",
            evidence="OCR text did not contain a recognizable number.",
            confidence=decl["confidence"] * 0.6,
            recommendation="Recapture the panel for a clearer read.",
        )
    low = rule.params.get("min", float("-inf"))
    high = rule.params.get("max", float("inf"))
    if low <= value <= high:
        return RuleEvalResult(
            rule, "PASS",
            finding=f"Declared value {value} falls within the expected range [{low}, {high}].",
            evidence=f"Detected text '{decl.get('detected_text')}' parsed as {value}.",
            confidence=decl["confidence"],
            recommendation="",
        )
    return RuleEvalResult(
        rule, "REVIEW",
        finding=f"Declared value {value} falls outside the plausible range [{low}, {high}] for this category.",
        evidence=f"Detected text '{decl.get('detected_text')}' parsed as {value}.",
        confidence=decl["confidence"] * 0.7,
        recommendation="An out-of-range reading is often an OCR error rather than an actual declaration problem — "
        "verify against the physical package before recording a finding.",
    )


def _eval_cross_field(rule: ComplianceRuleORM, declarations: list[dict]) -> RuleEvalResult:
    """
    `condition_type` present_implies_present -> if `if_declaration` is
    PRESENT, `then_declaration` must also be PRESENT. This is the hook for
    rules like "if a unit sale price is declared, net quantity must also be
    declared for the unit price to be meaningful."
    """
    if_type = rule.params.get("if_declaration")
    then_type = rule.params.get("then_declaration")
    condition_type = rule.params.get("condition_type", "present_implies_present")

    if_decl = _declaration_by_type(declarations, if_type)
    then_decl = _declaration_by_type(declarations, then_type)

    if_present = bool(if_decl and if_decl["status"] == "PRESENT")
    then_present = bool(then_decl and then_decl["status"] == "PRESENT")

    if condition_type == "present_implies_present":
        if not if_present:
            return RuleEvalResult(
                rule, "PASS",
                finding=f"{if_type.replace('_', ' ').title()} is not declared, so this cross-field rule does not apply.",
                evidence="Condition not triggered.",
                confidence=0.7,
                recommendation="",
            )
        if then_present:
            return RuleEvalResult(
                rule, "PASS",
                finding=f"{then_type.replace('_', ' ').title()} is declared alongside {if_type.replace('_', ' ').title()}, as required.",
                evidence=f"Both declarations detected.",
                confidence=0.7,
                recommendation="",
            )
        return RuleEvalResult(
            rule, "FAIL",
            finding=f"{if_type.replace('_', ' ').title()} is declared but {then_type.replace('_', ' ').title()} is missing.",
            evidence=f"{if_type} present, {then_type} not detected.",
            confidence=0.65,
            recommendation=f"Confirm whether {then_type.replace('_', ' ').title()} is genuinely absent from the package or simply not captured.",
        )

    return RuleEvalResult(
        rule, "REVIEW",
        finding=f"Unsupported cross-field condition_type '{condition_type}' — rule was not evaluated.",
        evidence="",
        confidence=0.0,
        recommendation="Correct this rule's params.condition_type in Rule Management.",
    )


def _eval_barcode_match(rule: ComplianceRuleORM, barcode_result: dict | None) -> RuleEvalResult:
    if barcode_result is not None and barcode_result.get("registryMatch") == "NOT_APPLICABLE":
        return RuleEvalResult(
            rule, "PASS",
            finding="Barcode/QR scanning does not apply to this product category.",
            evidence=barcode_result.get("note", ""),
            confidence=1.0,
            recommendation="",
        )
    if barcode_result is None or barcode_result.get("registryMatch") == "NOT_SCANNED":
        return RuleEvalResult(
            rule, "REVIEW",
            finding="Barcode was not scanned.",
            evidence="No barcode image/decoded value available.",
            confidence=0.5,
            recommendation="Capture a clear barcode image.",
        )
    match = barcode_result["registryMatch"]
    if match == "MATCH":
        return RuleEvalResult(rule, "PASS", finding="Barcode matches product registry.", evidence=barcode_result["note"], confidence=0.9, recommendation="")
    if match == "NOT_FOUND":
        return RuleEvalResult(
            rule, "REVIEW", finding="Barcode not found in registry.", evidence=barcode_result["note"],
            confidence=0.6, recommendation="Verify against manufacturer/GS1 records where available.",
        )
    return RuleEvalResult(
        rule, "REVIEW",
        finding="Potential counterfeit risk / verification required — barcode/product information mismatch.",
        evidence=barcode_result["note"],
        confidence=0.6,
        recommendation="Escalate for manual verification. A mismatch alone is not proof of counterfeiting.",
    )


EVALUATORS = {
    "PRESENCE": _eval_presence,
    "FORMAT": _eval_format,
    "FONT_SIZE": _eval_font_size,
    "READABILITY": _eval_readability,
    "TEXT_PATTERN": _eval_text_pattern,
    "NUMERIC": _eval_numeric,
    "RANGE": _eval_range,
    "CROSS_FIELD": _eval_cross_field,
}


def _rule_applies_to_category(rule: ComplianceRuleORM, category: str) -> bool:
    """
    `applicable_category` is either "ALL" or a comma-separated list of
    categories (e.g. "Cosmetics" or "Cosmetics,Household Chemicals"). This is
    the enforcement point for the brief's "applicability must depend on
    product category" requirement — a rule scoped to a category the
    inspection isn't in is skipped entirely rather than evaluated and
    ignored, so it never shows up in results or affects overall_status.
    """
    if rule.applicable_category in ("ALL", "", None):
        return True
    allowed = {c.strip() for c in rule.applicable_category.split(",")}
    return category in allowed


def evaluate_all(
    rules: list[ComplianceRuleORM],
    declarations: list[dict],
    barcode_result: dict | None,
    category: str = "ALL",
) -> list[RuleEvalResult]:
    results: list[RuleEvalResult] = []
    for rule in rules:
        if not rule.enabled:
            continue
        if not _rule_applies_to_category(rule, category):
            continue
        if rule.validation_type == "BARCODE_MATCH":
            results.append(_eval_barcode_match(rule, barcode_result))
        elif rule.validation_type in EVALUATORS:
            results.append(EVALUATORS[rule.validation_type](rule, declarations))
        else:
            # A rule was authored with a validation_type this engine doesn't
            # implement yet. Surface that as a REVIEW finding instead of
            # silently dropping it, so a misconfigured rule is visible to
            # the Administrator rather than invisibly doing nothing.
            results.append(
                RuleEvalResult(
                    rule, "REVIEW",
                    finding=f"Rule uses unimplemented validation_type '{rule.validation_type}'.",
                    evidence="",
                    confidence=0.0,
                    recommendation="Contact an administrator to correct this rule's validation_type.",
                )
            )
    return results


def overall_status(results: list[RuleEvalResult]) -> str:
    if any(r.status == "FAIL" and r.rule.severity in ("CRITICAL", "MAJOR") for r in results):
        return "NON_COMPLIANT"
    if any(r.status in ("FAIL", "REVIEW") for r in results):
        return "REVIEW_REQUIRED"
    return "COMPLIANT"


class GovRuleFeedAdapter:
    """
    Pluggable adapter for an official government rule-update feed.

    No such public API currently exists to connect to, so this adapter is
    disabled by default (GOV_RULE_FEED_ENABLED=false) rather than pointed at
    a fabricated endpoint. When an official feed is published, set
    GOV_RULE_FEED_URL and enable the flag — `fetch_updates()` already expects
    a JSON document following the same shape as
    `app/rules/legal_metrology_rules.yaml`.
    """

    def __init__(self, db: Session):
        self.db = db

    def enabled(self) -> bool:
        return settings.gov_rule_feed_enabled and bool(settings.gov_rule_feed_url)

    async def fetch_updates(self) -> dict[str, Any] | None:
        if not self.enabled():
            return None
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(settings.gov_rule_feed_url)
            response.raise_for_status()
            return response.json()

    def record_manual_import(self, version: str, source: str, change_summary: str) -> None:
        self.db.add(RuleVersionHistory(version=version, source=source, change_summary=change_summary))
        self.db.commit()
