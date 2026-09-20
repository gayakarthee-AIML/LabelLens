"""
Multimodal AI extraction adapter for the E-Commerce Listing feature.

HARD BOUNDARY (per the brief): this module extracts/classifies information
from unstructured content (listing text, product images) that the
deterministic regex pass in ecommerce_service.py / declaration_service.py
could not confidently find. It never decides PASS/FAIL/NEEDS_VERIFICATION —
only rule_engine.py does that. To make that boundary hard to accidentally
break rather than just documented, every field this module returns is
capped at `_MAX_AI_CONFIDENCE` and the caller (see the ecommerce analyze
endpoint in app/api/routers/inspections.py) marks every AI-sourced
declaration status "AMBIGUOUS" unconditionally, so it can only ever resolve
to a REVIEW finding in the rule engine — never an automatic PASS.

Uses the Anthropic Messages API (a real vision-capable model), lazily
imported and disabled by default when no API key is configured
(`Settings.anthropic_api_key`) — same pattern as `GovRuleFeedAdapter` in
rule_engine.py: no fabricated endpoint, a real integration that degrades to
"skip AI enrichment" rather than pretending to call something that isn't
configured.
"""
from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass

from app.core.config import get_settings

settings = get_settings()

_MAX_AI_CONFIDENCE = 0.6

# Maps each declaration type to a short human description used in the
# extraction prompt — kept here (not fabricated per-call) so the model is
# asked the same well-defined question every time.
_DECLARATION_DESCRIPTIONS = {
    "COMMON_NAME": "the common/generic name of the product",
    "NET_QUANTITY": "the declared net quantity (weight/volume/count), including its unit",
    "MRP": "the Maximum Retail Price, inclusive of all taxes",
    "MANUFACTURER_DETAILS": "the name and address of the manufacturer, packer, or importer",
    "COUNTRY_OF_ORIGIN": "the country of origin/manufacture",
    "MFG_DATE": "the month and year of manufacture or packing",
    "CONSUMER_CARE": "a consumer care / customer support contact (phone, email, or address)",
    "UNIT_SALE_PRICE": "the unit sale price (price per standard unit), if shown separately from MRP",
}


@dataclass
class AiExtractedField:
    declaration_type: str
    value: str
    confidence: float
    rationale: str


def enabled() -> bool:
    return settings.multimodal_enabled


def _build_prompt(missing_types: list[str], listing_text: str) -> str:
    questions = "\n".join(f"- {t}: {_DECLARATION_DESCRIPTIONS.get(t, t)}" for t in missing_types)
    return (
        "You are extracting factual product-label information from an e-commerce listing for a "
        "Legal Metrology compliance check. You are NOT deciding whether the product is compliant — "
        "only find and transcribe what is actually shown in the page text and/or images below.\n\n"
        f"Listing text (may be truncated):\n{listing_text[:4000]}\n\n"
        "For each of the following fields, look at the text and any attached images and report what "
        "you actually observe. If a field is not visible/stated anywhere, omit it entirely — do not "
        "guess or infer a plausible-sounding value.\n"
        f"{questions}\n\n"
        "Respond with ONLY a JSON array (no prose, no markdown fences), where each element is "
        '{"declaration_type": "...", "value": "the exact text/value observed", '
        '"confidence": 0.0-1.0, "rationale": "one short sentence on where you saw it"}.'
    )


def _parse_response_json(text: str) -> list[dict]:
    text = text.strip()
    # Strip ```json ... ``` fences if the model added them despite instructions.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        data = json.loads(text)
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def extract_missing_fields(
    missing_types: list[str],
    listing_text: str,
    image_bytes_list: list[bytes] | None = None,
) -> list[AiExtractedField]:
    """
    Asks the configured multimodal model to look for the given missing
    declaration types in the listing text and (optionally) product images.
    Returns an empty list — never raises — if the adapter is disabled, the
    API call fails, or the response can't be parsed, so a flaky/unconfigured
    AI call degrades to "no extra findings" rather than breaking the
    inspection.
    """
    if not enabled() or not missing_types:
        return []

    try:
        import anthropic  # imported lazily — optional dependency, only needed when configured

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        content: list[dict] = [{"type": "text", "text": _build_prompt(missing_types, listing_text)}]
        for img_bytes in (image_bytes_list or [])[:4]:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": base64.b64encode(img_bytes).decode("ascii"),
                    },
                }
            )

        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": content}],
        )
        text_blocks = [block.text for block in response.content if getattr(block, "type", None) == "text"]
        raw_items = _parse_response_json("\n".join(text_blocks))
    except Exception:
        # Network failure, bad API key, rate limit, malformed response, etc.
        # — the ecommerce analyze flow must still complete using whatever
        # the deterministic pass already found.
        return []

    results: list[AiExtractedField] = []
    for item in raw_items:
        decl_type = item.get("declaration_type")
        value = item.get("value")
        if decl_type not in missing_types or not value:
            continue
        confidence = min(_MAX_AI_CONFIDENCE, max(0.0, float(item.get("confidence", 0.4))))
        results.append(
            AiExtractedField(
                declaration_type=decl_type,
                value=str(value).strip(),
                confidence=confidence,
                rationale=str(item.get("rationale", "")).strip(),
            )
        )
    return results
