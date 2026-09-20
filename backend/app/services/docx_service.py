"""
Editable compliance report — DOCX, generated with python-docx so inspectors
and administrators can annotate/redact/adjust before an official filing.
"""
import io

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

from app.db.models import Inspection
from app.services import storage_service

INK = RGBColor(0x16, 0x21, 0x3E)
STATUS_COLORS = {
    "COMPLIANT": RGBColor(0x2E, 0x6F, 0x40),
    "NON_COMPLIANT": RGBColor(0xA6, 0x37, 0x3B),
    "REVIEW_REQUIRED": RGBColor(0xB9, 0x81, 0x2B),
    "DRAFT": RGBColor(0x5B, 0x64, 0x70),
}


def generate_docx_report(inspection: Inspection) -> bytes:
    doc = Document()

    title = doc.add_heading("LabelLens — Legal Metrology Compliance Report", level=1)
    title.runs[0].font.color.rgb = INK

    meta = doc.add_paragraph()
    meta.add_run(
        f"Inspection ID: {inspection.id}   |   Rule Version: {inspection.rule_version}   |   "
        f"Generated: {inspection.updated_at.strftime('%d %b %Y, %H:%M UTC')}"
    ).italic = True

    if inspection.source_type == "ECOMMERCE_LISTING":
        source_p = doc.add_paragraph()
        source_p.add_run(f"Source: E-Commerce Listing — {inspection.source_url}").italic = True

    table = doc.add_table(rows=4, cols=4)
    table.style = "Light Grid Accent 1"
    cells = table.rows
    data = [
        ("Product", inspection.product_name, "Brand", inspection.brand),
        ("Category", inspection.category, "Location", inspection.location or "—"),
        ("Inspector", inspection.inspector_name, "Role", inspection.inspector_role),
        ("Date/Time", inspection.created_at.strftime("%d %b %Y, %H:%M"), "Status", inspection.status.replace("_", " ")),
    ]
    for row, (k1, v1, k2, v2) in zip(cells, data):
        row.cells[0].text, row.cells[1].text, row.cells[2].text, row.cells[3].text = k1, v1, k2, v2

    doc.add_paragraph()
    status_p = doc.add_paragraph()
    status_run = status_p.add_run(f"Final Compliance Status: {inspection.status.replace('_', ' ')}")
    status_run.font.size = Pt(14)
    status_run.font.bold = True
    status_run.font.color.rgb = STATUS_COLORS.get(inspection.status, RGBColor(0, 0, 0))

    if inspection.barcode_raw_value:
        doc.add_paragraph(
            f"Barcode: {inspection.barcode_raw_value} ({inspection.barcode_symbology}) — "
            f"{inspection.barcode_registry_match.replace('_', ' ')}. {inspection.barcode_note}"
        )

    doc.add_heading("Mandatory Declarations", level=2)
    decl_table = doc.add_table(rows=1, cols=4)
    decl_table.style = "Light List Accent 1"
    hdr = decl_table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "Declaration", "Detected Text", "Confidence", "Status"
    for d in inspection.declarations:
        row = decl_table.add_row().cells
        row[0].text = d["declaration_type"].replace("_", " ").title()
        row[1].text = d.get("detected_text") or "Not detected"
        row[2].text = f"{d.get('confidence', 0):.0%}"
        row[3].text = d["status"]
        # Inspectors editing this DOCX can freely retype the "Detected Text"
        # cell — that is the whole point of an editable report format.

    doc.add_heading("Rule Compliance Findings", level=2)
    rule_table = doc.add_table(rows=1, cols=4)
    rule_table.style = "Light List Accent 1"
    hdr = rule_table.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text, hdr[3].text = "Rule", "Status", "Finding", "Severity"
    for r in inspection.rule_results:
        row = rule_table.add_row().cells
        row[0].text = f"{r['rule']['ruleId']} — {r['rule']['name']}"
        row[1].text = r["status"]
        row[2].text = r["finding"]
        row[3].text = r["rule"]["severity"]

    if inspection.images:
        doc.add_heading("Photographic Evidence", level=2)
        for img in inspection.images[:4]:
            try:
                image_bytes = storage_service.get_object(img.storage_key)
                doc.add_paragraph(img.slot.title())
                doc.add_picture(io.BytesIO(image_bytes), width=Inches(2.5))
            except Exception:
                doc.add_paragraph(f"{img.slot.title()}: image unavailable in storage.")

    if inspection.notes:
        doc.add_heading("Inspector Remarks", level=2)
        doc.add_paragraph(inspection.notes)

    footer = doc.add_paragraph()
    footer.alignment = WD_ALIGN_PARAGRAPH.LEFT
    footer_run = footer.add_run(
        "Editable report — AI-assisted findings marked REVIEW require human verification. "
        "Edits made in this document should be reconciled back into LabelLens before final filing."
    )
    footer_run.italic = True
    footer_run.font.size = Pt(8.5)

    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
