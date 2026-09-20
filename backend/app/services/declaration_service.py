"""
Declaration extraction from OCR output.

Takes the raw word list PaddleOCR returned for an image (see ocr_service.py)
and classifies which Legal Metrology declarations are present, using regex
patterns against the actual recognized text — not a fixed template assumed
to apply to every product. Applicability of a given declaration to a given
product category is decided by the rule engine (rule_engine.py), which reads
`applicable_category` off each rule; this module only reports what text was
found and where.
"""
import re
from dataclasses import dataclass

from app.services.ocr_service import OcrWord, estimate_text_height_px

# Each pattern is tried against the OCR text of a slot image. Patterns are
# intentionally permissive (declarations are printed inconsistently) but
# still real regexes matched against real text, not fabricated matches.
DECLARATION_PATTERNS: dict[str, list[str]] = {
    # MRP and MANUFACTURER_DETAILS are handled separately below, not through
    # this generic loop — both need extra logic this simple loop can't do
    # (currency-token validation for MRP; implausible-match rejection and
    # retry for MANUFACTURER_DETAILS — see their dedicated functions).
    "NET_QUANTITY": [
        # "Nett" (double-T) is a common spelling on Indian labels — "Net"
        # alone didn't match it due to the word boundary. `Nett?` matches both.
        # Unit list now also includes "N"/"Nos"/"pcs"/"units" — Legal
        # Metrology allows count-based net quantity for items sold by piece
        # (notebooks, pens, etc.) using "N" (Number) as the unit, e.g.
        # "Net Quantity : 4 N" — the original weight/volume-only unit list
        # couldn't match this at all.
        r"\bNett?\s*(?:Qty|Quantity|Wt\.?|Weight)?[:\-\s]*([\d.]+\s?(?:g|kg|gm|gms|ml|l|ltr|litre|N|Nos\.?|pcs|pieces|units?)s?\.?)",
    ],
    # MANUFACTURER_DETAILS is handled by _extract_manufacturer_details()
    # below, not through this dict/loop — see that function's docstring.
    "COUNTRY_OF_ORIGIN": [
        r"\bCountry\s+of\s+Origin[:\-\s]*([A-Za-z ]{3,40})",
    ],
    "MFG_DATE": [
        # "Manufacturing Date" (the -ing form) is at least as common as
        # "Manufactured Date" on real labels — only the latter matched before.
        # "Mfd" added alongside "Mfg" — both are common date-field
        # abbreviations on real labels (e.g. a standalone "MFD :" field).
        r"\b(?:Mfg|Mfd|Manufactured|Manufacturing|Packed|Pkd)\.?\s*(?:Date|On|Dt)?[:\-\s]*"
        r"((?:\d{1,2}[/\-])?\d{1,2}[/\-]\d{2,4}|[A-Za-z]{3,9}\s?\d{4})",
    ],
    "CONSUMER_CARE": [
        r"\b(?:Consumer\s+Care|Customer\s+Care|Helpline|For\s+Complaints)[:\-\s]*([^\n]{5,120})",
    ],
    "UNIT_SALE_PRICE": [
        r"\bUnit\s+Sale\s+Price[:\-\s]*(?:Rs\.?|₹)?\s*([\d,]+(?:\.\d{1,2})?)",
    ],
    # COMMON_NAME has no reliable regex signature — every other declaration
    # co-occurring with a plausible product noun phrase is treated as a weak
    # signal of presence; see extract_common_name below.
}


@dataclass
class ExtractedDeclaration:
    declaration_type: str
    detected_text: str | None
    confidence: float
    bounding_box: dict | None
    source_image: str
    status: str  # PRESENT | MISSING | AMBIGUOUS
    estimated_text_height_px: float | None
    readability: str | None


def _find_matching_word(pattern_match_text: str, words: list[OcrWord]) -> OcrWord | None:
    """Best-effort: find the OCR word/line whose text contains the matched fragment,
    so we can report a bounding box and confidence for the declaration."""
    fragment = pattern_match_text.strip().lower()[:12]
    for w in words:
        if fragment and fragment in w.text.lower():
            return w
    return None


def _readability_for(word: OcrWord | None, glare_pct: float, blur_score: float) -> str | None:
    if word is None:
        return None
    if word.confidence >= 0.85 and glare_pct < 0.1 and blur_score >= 60:
        return "GOOD"
    if word.confidence < 0.5 or glare_pct > 0.2 or blur_score < 30:
        return "POOR"
    return "REVIEW"


def _box_y_center(box: list[list[float]]) -> float:
    ys = [p[1] for p in box]
    return (min(ys) + max(ys)) / 2


def _box_x_left(box: list[list[float]]) -> float:
    return min(p[0] for p in box)


def _box_x_right(box: list[list[float]]) -> float:
    return max(p[0] for p in box)


def _box_height(box: list[list[float]]) -> float:
    ys = [p[1] for p in box]
    return max(ys) - min(ys)


def _find_spatial_value(
    words: list[OcrWord], label_pattern: "re.Pattern[str]", value_pattern: "re.Pattern[str]"
):
    """
    Row-based spatial pairing for label:value table layouts — e.g. "Nett
    Weight" printed on the left with "100 g" in a separate column to the
    right. A plain text-adjacency regex can't handle this when PaddleOCR
    detects the label and its value as two SEPARATE text boxes rather than
    one continuous line (very common on Indian labels with a two-column
    declarations table), which is exactly the case that was silently
    returning MISSING before this existed.

    Finds a word matching `label_pattern`, then looks among the OTHER words
    on the same image for ones whose vertical center is close to the
    label's (i.e. roughly the same printed "row"), preferring ones to its
    right (the standard label-left/value-right layout) but not requiring
    it, since real photos are rarely perfectly aligned. Critically, a
    candidate is only accepted if its OWN text matches `value_pattern` —
    this is what keeps the fallback safe: it will not just grab whatever
    number happens to be nearest (e.g. a lot number), only something that
    already looks like a valid value of the expected shape (a quantity+unit,
    a date, a price). Returns (matched_word, match) or None.
    """
    label_word = next((w for w in words if label_pattern.search(w.text)), None)
    if label_word is None:
        return None

    label_y = _box_y_center(label_word.box)
    label_height = _box_height(label_word.box) or 20.0
    # Generous but bounded — real photos are rarely perfectly row-aligned
    # across columns, but this shouldn't drift into an unrelated row.
    y_tolerance = max(25.0, label_height * 1.5)

    candidates = []
    for w in words:
        if w is label_word:
            continue
        w_y = _box_y_center(w.box)
        if abs(w_y - label_y) > y_tolerance:
            continue
        match = value_pattern.search(w.text)
        if not match:
            continue
        is_rightward = _box_x_left(w.box) >= _box_x_right(label_word.box) - 10
        # Prefer closer rows; among equally-close rows, prefer the expected
        # rightward (label-left/value-right) layout over a leftward match.
        score = abs(w_y - label_y) - (5 if is_rightward else 0)
        candidates.append((score, w, match))

    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    _, best_word, best_match = candidates[0]
    return best_word, best_match


# Label/value pattern pairs for the spatial fallback, covering the
# "tabular" declarations most likely to be split across two OCR-detected
# columns (a distinct field-name column and a distinct value column).
# MRP has its own label/value pair defined near _extract_mrp() below, since
# it needs the extra currency-token handling that function already does.
# MANUFACTURER_DETAILS/CONSUMER_CARE aren't included here — those are
# printed as continuous prose ("Manufactured by X, address...") rather than
# a table row, so they don't suffer from this column-split problem in the
# first place, and a free-text value pattern for them would be too
# unconstrained to safely spatially match. COUNTRY_OF_ORIGIN is excluded
# for the same reason: there's no reliable way to validate that a nearby
# short alphabetic word is actually a country name via regex alone (a real
# country-name list would be needed), so a spatial fallback here would risk
# matching unrelated nearby text with false confidence — left on
# text-adjacency matching only rather than guessing.
_SPATIAL_LABEL_PATTERNS: dict[str, "re.Pattern[str]"] = {
    "NET_QUANTITY": re.compile(r"\bNett?\s*(?:Qty|Quantity|Wt\.?|Weight)?\b", re.IGNORECASE),
    "MFG_DATE": re.compile(r"\b(?:Mfg|Mfd|Manufactured|Manufacturing|Packed|Pkd)\.?\s*(?:Date|On|Dt)?\b", re.IGNORECASE),
    "UNIT_SALE_PRICE": re.compile(r"\bUnit\s+Sale\s+Price\b", re.IGNORECASE),
}
_SPATIAL_VALUE_PATTERNS: dict[str, "re.Pattern[str]"] = {
    "NET_QUANTITY": re.compile(r"^\s*([\d.]+\s?(?:g|kg|gm|gms|ml|l|ltr|litre|N|Nos\.?|pcs|pieces|units?)s?\.?)\s*$", re.IGNORECASE),
    "MFG_DATE": re.compile(r"^\s*((?:\d{1,2}[/\-])?\d{1,2}[/\-]\d{2,4}|[A-Za-z]{3,9}\s?\d{4})\s*$", re.IGNORECASE),
    "UNIT_SALE_PRICE": re.compile(r"^\s*(?:Rs\.?|₹|INR)?\s*([\d,]+(?:[.\-]\d{1,2})?)\s*$", re.IGNORECASE),
}


def extract_declarations(
    words_by_slot: dict[str, list[OcrWord]],
    quality_by_slot: dict[str, dict],
) -> list[ExtractedDeclaration]:
    results: list[ExtractedDeclaration] = []

    for declaration_type, patterns in DECLARATION_PATTERNS.items():
        found_decl: ExtractedDeclaration | None = None
        for slot, words in words_by_slot.items():
            full_text = "\n".join(w.text for w in words)
            match = None
            matched_word = None
            for pattern in patterns:
                m = re.search(pattern, full_text, re.IGNORECASE)
                if m:
                    match = m
                    matched_word = _find_matching_word(m.group(0), words)
                    break

            is_spatial = False
            if match is None and declaration_type in _SPATIAL_LABEL_PATTERNS:
                spatial_result = _find_spatial_value(
                    words, _SPATIAL_LABEL_PATTERNS[declaration_type], _SPATIAL_VALUE_PATTERNS[declaration_type]
                )
                if spatial_result:
                    matched_word, match = spatial_result
                    is_spatial = True

            if match is None:
                continue

            # "webpage" is synthetic text, not a photographed image — it has
            # no real pixel bounding box to measure a physical font size or
            # image-quality-based readability from. Forcing these to None
            # here (rather than letting a placeholder value flow through) is
            # the fix for a bug where webpage-sourced declarations were
            # fabricating a passing font-size/readability result. See
            # rule_engine.py's _NON_PHYSICAL_SOURCES for the corresponding
            # rule-side guard.
            is_physical_source = slot != "webpage"
            text_height = estimate_text_height_px(matched_word) if (matched_word and is_physical_source) else None
            quality = quality_by_slot.get(slot, {})
            readability = (
                _readability_for(matched_word, quality.get("glare_pct", 0.0), quality.get("blur_score", 100.0))
                if is_physical_source else None
            )
            confidence = matched_word.confidence if matched_word else 0.6
            if is_spatial:
                # A spatially-paired match stitched two SEPARATE OCR
                # detections together by position rather than reading one
                # continuous string, so it's inherently a little less
                # certain than a direct text match — capped, not zeroed out.
                confidence = min(0.75, confidence)
            found_decl = ExtractedDeclaration(
                declaration_type=declaration_type,
                detected_text=match.group(1).strip() if match.groups() else match.group(0).strip(),
                confidence=confidence,
                bounding_box=_box_to_dict(matched_word.box) if matched_word else None,
                source_image=slot,
                status="PRESENT",
                estimated_text_height_px=text_height,
                readability=readability,
            )
            break

        results.append(
            found_decl
            or ExtractedDeclaration(
                declaration_type=declaration_type,
                detected_text=None,
                confidence=0.0,
                bounding_box=None,
                source_image="front",
                status="MISSING",
                estimated_text_height_px=None,
                readability=None,
            )
        )

    results.append(_extract_common_name(words_by_slot))
    results.append(_extract_mrp(words_by_slot))
    results.append(_extract_manufacturer_details(words_by_slot))
    _apply_bare_net_quantity_fallback(results, words_by_slot)
    return results


# Some real labels print net quantity as a bare "500g" near the barcode,
# with NO "Net Weight"/"Nett Qty" keyword anywhere nearby — the primary
# and spatial-pairing patterns above both require that keyword and can't
# find this. A blind "any number+unit" fallback would be dangerous: a
# nutrition facts panel is full of numbers sharing the same units (e.g.
# "2g" poly-unsaturated fat, "0g" trans fat) that could get grabbed instead
# of the real net quantity. This fallback is deliberately narrow to avoid
# that — verified against a real label's actual nutrition table (Britannia
# Milk Bikis) before shipping, see the test suite:
#   - requires a WHOLE number (2-5 digits) directly adjacent to the unit
#     with NO space ("500g", not "8.5 g" or "2 g") — matches how net
#     quantity is conventionally printed on Indian packaging, and excludes
#     virtually every nutrition-table entry, which is printed "value unit"
#     WITH a space and is usually decimal
#   - the unit is restricted to g/kg/ml/l specifically (not mg/mcg/kcal,
#     which nutrition tables use for micronutrients and energy)
#   - the value must fall in a plausible package-size range, excluding tiny
#     single-digit nutrition amounts like "2g"/"0g" even in the unlikely
#     case they were printed without a space
# Even with all that, this is inherently a guess — no explicit label
# confirms this number IS the net quantity — so it is ALWAYS reported as
# AMBIGUOUS, never a confident PRESENT, prompting a human check rather than
# asserting a fact. Only used when the labeled patterns above found nothing.
_BARE_QUANTITY_PATTERN = re.compile(r"\b(\d{2,5})(g|kg|ml|l)\b")
_BARE_QUANTITY_RANGES = {"g": (10, 10000), "kg": (0.01, 50), "ml": (10, 10000), "l": (0.01, 50)}


def _apply_bare_net_quantity_fallback(
    results: list[ExtractedDeclaration], words_by_slot: dict[str, list[OcrWord]]
) -> None:
    net_qty = next(d for d in results if d.declaration_type == "NET_QUANTITY")
    if net_qty.status != "MISSING":
        return  # a labeled match (direct or spatial) already found something — don't override it

    for slot, words in words_by_slot.items():
        for w in words:
            match = _BARE_QUANTITY_PATTERN.search(w.text)
            if not match:
                continue
            value, unit = float(match.group(1)), match.group(2)
            lo, hi = _BARE_QUANTITY_RANGES[unit]
            if not (lo <= value <= hi):
                continue
            is_physical_source = slot != "webpage"
            net_qty.detected_text = match.group(0)
            net_qty.confidence = min(0.55, w.confidence)
            net_qty.bounding_box = _box_to_dict(w.box)
            net_qty.source_image = slot
            net_qty.status = "AMBIGUOUS"
            net_qty.estimated_text_height_px = estimate_text_height_px(w) if is_physical_source else None
            net_qty.readability = None
            return


# Text that clearly isn't a company name/address, even though it may follow
# a manufacturer-ish keyword in raw reading order — catches the exact
# failure mode above where an unrelated nearby line (allergen/ingredient/
# nutrition text) gets captured instead of the real address.
_IMPLAUSIBLE_MANUFACTURER_PATTERN = re.compile(
    r"^\s*(?:contains?\b|ingredients?\b|nutrition|nutrient|allergen|best\s+before|batch\s+no|lot\s+no|"
    r"storage|store\s+in|keep\s+away)",
    re.IGNORECASE,
)
# A candidate line that ITSELF looks like a distinct field's label (a short
# ONE- OR TWO-WORD phrase immediately followed by a colon, e.g. "Product :
# Notebook", "Size :", "Ruling :") — a strong signal we've wandered into a
# DIFFERENT field entirely, not a continuation of the manufacturer's
# address. Deliberately capped at two words (not "any short phrase up to 20
# chars") — a real company name can easily be short too ("Kokuyo Camlin
# Ltd:", three words) and an overly broad version of this pattern rejected
# those as false positives during testing.
_LOOKS_LIKE_OTHER_FIELD_PATTERN = re.compile(r"^\s*[A-Za-z]+(?:\s[A-Za-z]+)?\s*:")
# "Mfd"/"Mfg" are genuinely ambiguous abbreviations on real labels — they're
# used for BOTH "Manufactured by" AND "Manufacturing Date" ("MFD :" as its
# own date field, e.g. right next to "Product :" on a spec-sheet-style
# label). The full words (Manufactured/Manufacturer/Marketed/etc.) aren't
# ambiguous and don't need disambiguating, but a bare "Mfd"/"Mfg" is only
# treated as a manufacturer trigger when directly followed by "by" — this
# is what stops a "MFD :" date field from being misread as "Manufactured
# by" and having the extractor go hunting below it for an address.
#
# Split into two priority tiers rather than one combined keyword set: real
# labels often print BOTH "Marketed by: <company>" AND, separately,
# "Manufactured by: <different company>" (a marketer/distributor and the
# actual manufacturing plant are frequently different entities). Since this
# declaration is specifically Manufacturer/Packer/Importer, an exact
# "Manufactured"/"Manufacturer"/"Mfd by"/"Mfg by"/"Packed"/"Packer"/
# "Imported"/"Importer" match should always be preferred when the label has
# one, rather than stopping at whichever keyword happens to appear first in
# reading order. "Marketed"/"Mktd"/"Distributed" are only used as a
# fallback if no primary-tier match is found anywhere.
_MANUFACTURER_PRIMARY_CORE = (
    r"Manufactured|Manufacturer|Packed|Packer|Imported|Importer|Mfd\.?\s*by|Mfg\.?\s*by"
)
_MANUFACTURER_FALLBACK_CORE = r"Marketed(?:\s*(?:&|and)\s*Distributed)?|Mktd|Distributed"


def _manufacturer_patterns(core: str) -> tuple["re.Pattern[str]", "re.Pattern[str]"]:
    keyword = re.compile(rf"\b(?:{core})\b", re.IGNORECASE)
    inline = re.compile(rf"\b(?:{core})\.?\s*(?:by)?[:\-\ \t]+(\S[^\n]{{4,160}})", re.IGNORECASE)
    return keyword, inline


_MANUFACTURER_PRIMARY_KEYWORD, _MANUFACTURER_PRIMARY_INLINE = _manufacturer_patterns(_MANUFACTURER_PRIMARY_CORE)
_MANUFACTURER_FALLBACK_KEYWORD, _MANUFACTURER_FALLBACK_INLINE = _manufacturer_patterns(_MANUFACTURER_FALLBACK_CORE)


def _is_plausible_manufacturer_text(text: str) -> bool:
    return not (_IMPLAUSIBLE_MANUFACTURER_PATTERN.match(text) or _LOOKS_LIKE_OTHER_FIELD_PATTERN.match(text))


def _search_manufacturer_tier(
    words_by_slot: dict[str, list[OcrWord]], keyword_pattern: "re.Pattern[str]", inline_pattern: "re.Pattern[str]"
) -> ExtractedDeclaration | None:
    for slot, words in words_by_slot.items():
        for w in words:
            inline = inline_pattern.search(w.text)
            if inline and _is_plausible_manufacturer_text(inline.group(1).strip()):
                return _manufacturer_result(slot, w, inline.group(1).strip())

            # A short line that's essentially just the keyword itself (e.g.
            # "Manufactured by :") with no real content on it — look for
            # the nearest plausible text physically below it.
            if keyword_pattern.search(w.text) and len(w.text.strip()) < 40 and not inline:
                label_y = _box_y_center(w.box)
                below = sorted(
                    (cw for cw in words if cw is not w and _box_y_center(cw.box) > label_y),
                    key=lambda cw: _box_y_center(cw.box),
                )
                for candidate_word in below[:6]:
                    candidate = candidate_word.text.strip()
                    if len(candidate) < 5 or not _is_plausible_manufacturer_text(candidate):
                        continue
                    return _manufacturer_result(slot, candidate_word, candidate)
    return None


def _extract_manufacturer_details(words_by_slot: dict[str, list[OcrWord]]) -> ExtractedDeclaration:
    """
    Two cases per tier (primary: Manufactured/Manufacturer/Packed/Packer/
    Imported/Importer/Mfd by/Mfg by; fallback: Marketed/Mktd/Distributed,
    only tried if the primary tier finds nothing — see the tier constants'
    docstring above for why they're split):

    A) "Manufactured by: XYZ Ltd, address" — keyword + content on the SAME
       OCR-detected line, handled directly.
    B) "Manufactured by :" alone on its own short line, with the actual
       address printed below it — this is the common case on structured/
       grid-style labels (a bordered spec sheet with separate cells for
       Product, Size, MRP, Manufactured by, etc.), and it needs POSITION,
       not just OCR reading order, to find the right continuation: only
       candidates whose bounding box is physically BELOW the label (higher
       y-coordinate) are considered, sorted nearest-first. Plain array-order
       "look at the next few OCR results" was the actual bug here — on a
       dense grid label, the next few entries in reading order can easily
       belong to a totally different, unrelated cell (e.g. "Product :
       Notebook" from the row above), and array order doesn't reflect
       spatial adjacency the way a simple list scan seems to imply.

    Both cases are further guarded by _is_plausible_manufacturer_text() so
    a candidate that's either obviously unrelated content (allergen/
    ingredient/nutrition text) or is itself clearly a different field's
    label ("Product :", "Size :") is never accepted — this is what stops
    the extractor from confidently reporting something like "CONTAINS
    WHEAT,MILK,SOY" or "Product:Notebook" as the manufacturer, both of
    which happened before these checks existed.

    If nothing plausible is found anywhere in either tier, this reports
    MISSING rather than a wrong-but-confident-looking result — for a legal
    declaration, an honest "not found" is safer than a confident wrong answer.
    """
    return (
        _search_manufacturer_tier(words_by_slot, _MANUFACTURER_PRIMARY_KEYWORD, _MANUFACTURER_PRIMARY_INLINE)
        or _search_manufacturer_tier(words_by_slot, _MANUFACTURER_FALLBACK_KEYWORD, _MANUFACTURER_FALLBACK_INLINE)
        or ExtractedDeclaration(
            declaration_type="MANUFACTURER_DETAILS",
            detected_text=None,
            confidence=0.0,
            bounding_box=None,
            source_image="front",
            status="MISSING",
            estimated_text_height_px=None,
            readability=None,
        )
    )


def _manufacturer_result(slot: str, matched_word: OcrWord, text: str) -> ExtractedDeclaration:
    is_physical_source = slot != "webpage"
    return ExtractedDeclaration(
        declaration_type="MANUFACTURER_DETAILS",
        detected_text=text,
        confidence=matched_word.confidence,
        bounding_box=_box_to_dict(matched_word.box),
        source_image=slot,
        status="PRESENT",
        estimated_text_height_px=estimate_text_height_px(matched_word) if is_physical_source else None,
        readability=None,
    )


# MRP is a legally load-bearing number, and PaddleOCR's character dictionary
# very likely doesn't include ₹ (the Indian Rupee sign) at all — a widely
# reported real limitation, not something fixable by a better regex. When
# the model hits a glyph it's never seen, it substitutes the closest thing
# it does know, which for ₹ is very commonly a stray digit (e.g. "2"). That
# digit then looks textually identical to a genuine leading digit of the
# price — "₹199.00" misread as "2199.00" cannot be distinguished from a
# real "₹2199.00" by looking at the text alone; there is no reliable way to
# strip it back out.
#
# So rather than silently trusting whatever digits follow "MRP" (the
# previous behavior — which is where a misread symbol got invisibly glued
# onto the front of a wrong-but-confident-looking number), this only marks
# the price PRESENT when a clean, recognizable currency token (Rs./₹/INR)
# was actually found. If none was, the extracted digits are still reported
# (so the inspector isn't left with a blank field) but the status is
# AMBIGUOUS with an explicit note — which, per rule_engine.py's presence
# check, becomes a REVIEW finding rather than a confident PASS, prompting
# a human to actually check the photographed image before relying on the
# number. This is a deliberate accuracy-over-confidence tradeoff for a
# legally consequential figure, not an oversight.
_MRP_PATTERN = re.compile(
    # "MRP" / "M.R.P." and the fully spelled-out "Maximum Retail Price" are
    # both common — only the abbreviation matched before. "(Inclusive of all
    # Taxes)" is near-universal companion text on real MRP declarations
    # (often legally required alongside it) and commonly OCRs as its own
    # line between the label and the actual price — explicitly tolerating
    # it here (rather than broadly skipping arbitrary text, which risks
    # latching onto an unrelated nearby number, e.g. a lot number) is a
    # targeted, safe fix for a real, common layout, not a blind guess.
    # The price itself may use a dash before the paise ("Rs.29-00") instead
    # of a decimal point ("Rs.29.00") — both are real Indian label conventions.
    r"\b(?:M\.?R\.?P\.?|Maximum\s+Retail\s+Price)\.?[:\-\s]*"
    r"(?:\(?\s*Incl(?:usive)?\.?\s+of\s+all\s+Taxes\s*\)?)?"
    r"[:\-\s]*(Rs\.?|₹|INR)?\s*([\d,]+(?:[.\-]\d{1,2})?)",
    re.IGNORECASE,
)
# Spatial fallback for when "Maximum Retail Price" and "Rs.29-00" are two
# SEPARATE OCR-detected boxes (the two-column table layout) rather than one
# continuous line — see _find_spatial_value()'s docstring.
_MRP_LABEL_PATTERN = re.compile(r"\b(?:M\.?R\.?P\.?|Maximum\s+Retail\s+Price)\b", re.IGNORECASE)
_MRP_VALUE_PATTERN = re.compile(r"^\s*(Rs\.?|₹|INR)?\s*([\d,]+(?:[.\-]\d{1,2})?)\s*$", re.IGNORECASE)


def _extract_mrp(words_by_slot: dict[str, list[OcrWord]]) -> ExtractedDeclaration:
    for slot, words in words_by_slot.items():
        full_text = "\n".join(w.text for w in words)
        match = _MRP_PATTERN.search(full_text)
        matched_word = _find_matching_word(match.group(0), words) if match else None
        is_spatial = False

        if match is None:
            spatial_result = _find_spatial_value(words, _MRP_LABEL_PATTERN, _MRP_VALUE_PATTERN)
            if spatial_result is None:
                continue
            matched_word, match = spatial_result
            is_spatial = True

        currency_token, price = match.group(1), match.group(2)
        is_physical_source = slot != "webpage"
        if currency_token:
            confidence = matched_word.confidence if matched_word else 0.7
            if is_spatial:
                confidence = min(0.75, confidence)
            return ExtractedDeclaration(
                declaration_type="MRP",
                detected_text=price,
                confidence=confidence,
                bounding_box=_box_to_dict(matched_word.box) if matched_word else None,
                source_image=slot,
                status="PRESENT",
                estimated_text_height_px=estimate_text_height_px(matched_word) if (matched_word and is_physical_source) else None,
                readability=None,
            )
        return ExtractedDeclaration(
            declaration_type="MRP",
            detected_text=price,
            confidence=min(0.5, matched_word.confidence if matched_word else 0.5),
            bounding_box=_box_to_dict(matched_word.box) if matched_word else None,
            source_image=slot,
            status="AMBIGUOUS",
            estimated_text_height_px=None,
            readability=None,
        )
    return ExtractedDeclaration(
        declaration_type="MRP",
        detected_text=None,
        confidence=0.0,
        bounding_box=None,
        source_image="front",
        status="MISSING",
        estimated_text_height_px=None,
        readability=None,
    )


# Boilerplate/instruction phrases that are sometimes printed in a larger or
# bolder font than the actual product name (e.g. "BEST BEFORE THREE MONTHS
# FROM MANUFACTURING" as a prominent banner line) — the plain "pick the
# largest text on the panel" heuristic can latch onto one of these instead
# of the real name. Filtering them out of the candidate pool first is a
# targeted, testable fix for that specific failure mode.
#
# This does NOT fix OCR misreading a stylized/decorative logo font as an
# unrelated dictionary-like word — that's a genuine limitation of the
# underlying model's character recognition on fonts far outside its
# training distribution, and no amount of regex or post-processing can
# recover text the model fundamentally misread. What this DOES do is stop
# treating a low-confidence or implausible-looking candidate as a confident
# fact: it's marked AMBIGUOUS (-> REVIEW in the rule engine) instead of
# PRESENT, so a misread logo prompts a human check rather than silently
# becoming "the product name" in a compliance report.
_NON_NAME_PATTERN = re.compile(
    r"^\s*(?:best\s+before|batch\s+no|lot\s+no|mfg|exp(?:iry)?|net\s*wt|nett?\s+weight|"
    r"ingredients?|nutrition|nutrient|contains|store\s+in|keep\s+away)\b",
    re.IGNORECASE,
)


def _extract_common_name(words_by_slot: dict[str, list[OcrWord]]) -> ExtractedDeclaration:
    # Physical inspections always have a "front" slot; e-commerce listings
    # never do (their slots are "webpage" / "ecommerce_image_N"). Falling
    # back to whichever slot actually has words — rather than only ever
    # checking "front" — is the fix for a bug where COMMON_NAME was
    # structurally guaranteed to come back MISSING for every e-commerce
    # listing regardless of how good the extraction otherwise was.
    candidate_slot = "front" if words_by_slot.get("front") else next(
        (slot for slot, words in words_by_slot.items() if words), None
    )
    front_words = words_by_slot.get(candidate_slot, []) if candidate_slot else []
    if not front_words:
        return ExtractedDeclaration(
            declaration_type="COMMON_NAME",
            detected_text=None,
            confidence=0.0,
            bounding_box=None,
            source_image="front",
            status="MISSING",
            estimated_text_height_px=None,
            readability=None,
        )
    is_physical_source = candidate_slot != "webpage"

    plausible = [
        w for w in front_words
        if len(w.text.strip()) >= 3 and not _NON_NAME_PATTERN.match(w.text) and not w.text.strip().replace(" ", "").isdigit()
    ]
    # If filtering removed every candidate (e.g. a panel that's genuinely
    # all boilerplate/nutrition text with nothing name-like on it), fall
    # back to the unfiltered pool rather than reporting nothing at all —
    # but this fallback case is exactly why `used_fallback_pool` below
    # forces AMBIGUOUS rather than a confident PASS.
    pool = plausible or front_words
    used_fallback_pool = not plausible

    # Heuristic: the largest (by bounding-box height), highest-confidence line
    # on the panel is usually the product/common name — a real, measurable
    # signal from the OCR output on a physical image. Webpage text has no
    # real bounding-box height to rank by (see extract_declarations above),
    # so for that source this just takes the highest-confidence line instead.
    if is_physical_source:
        candidate = max(pool, key=lambda w: (estimate_text_height_px(w), w.confidence))
    else:
        candidate = max(pool, key=lambda w: w.confidence)

    status = "PRESENT" if (candidate.confidence > 0.4 and not used_fallback_pool) else "AMBIGUOUS"
    return ExtractedDeclaration(
        declaration_type="COMMON_NAME",
        detected_text=candidate.text,
        confidence=candidate.confidence,
        bounding_box=_box_to_dict(candidate.box),
        source_image=candidate_slot,
        status=status,
        estimated_text_height_px=estimate_text_height_px(candidate) if is_physical_source else None,
        readability=None,
    )


def _box_to_dict(box: list[list[float]]) -> dict:
    xs = [p[0] for p in box]
    ys = [p[1] for p in box]
    return {"x": min(xs), "y": min(ys), "width": max(xs) - min(xs), "height": max(ys) - min(ys)}
