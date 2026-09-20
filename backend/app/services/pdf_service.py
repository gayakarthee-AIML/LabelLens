"""
Official inspection report — PDF, generated with ReportLab (as required by
the brief). Every field pulled onto the report comes from the Inspection ORM
record; nothing is templated placeholder text.
"""
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
)

from app.db.models import Inspection
from app.services import storage_service

STYLES = getSampleStyleSheet()
STYLES.add(ParagraphStyle(name="LLTitle", fontSize=18, leading=22, spaceAfter=4, textColor=colors.HexColor("#16213E")))
STYLES.add(ParagraphStyle(name="LLSub", fontSize=10, textColor=colors.HexColor("#5B6470"), spaceAfter=12))
STYLES.add(ParagraphStyle(name="LLSection", fontSize=13, spaceBefore=14, spaceAfter=6, textColor=colors.HexColor("#16213E")))

STATUS_COLORS = {
    "COMPLIANT": colors.HexColor("#2E6F40"),
    "NON_COMPLIANT": colors.HexColor("#A6373B"),
    "REVIEW_REQUIRED": colors.HexColor("#B9812B"),
    "DRAFT": colors.HexColor("#5B6470"),
}


def _declaration_table(declarations: list[dict]) -> Table:
    header = ["Declaration", "Detected Text", "Confidence", "Status"]
    rows = [header]
    for d in declarations:
        rows.append(
            [
                d["declaration_type"].replace("_", " ").title(),
                (d.get("detected_text") or "Not detected")[:60],
                f"{d.get('confidence', 0):.0%}",
                d["status"],
            ]
        )
    table = Table(rows, colWidths=[110 * mm / 3, 110 * mm, 90 * mm / 3, 60 * mm / 2])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D2C4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _rule_table(rule_results: list[dict]) -> Table:
    header = ["Rule", "Status", "Finding", "Severity"]
    rows = [header]
    for r in rule_results:
        rows.append(
            [
                f"{r['rule']['ruleId']}\n{r['rule']['name']}",
                r["status"],
                r["finding"][:90],
                r["rule"]["severity"],
            ]
        )
    table = Table(rows, colWidths=[100 * mm / 2, 50 * mm / 2, 200 * mm / 2, 50 * mm / 2])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D8D2C4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def generate_pdf_report(inspection: Inspection) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=18 * mm, bottomMargin=18 * mm)
    story = []

    story.append(Paragraph("LabelLens — Legal Metrology Compliance Report", STYLES["LLTitle"]))
    story.append(
        Paragraph(
            f"Inspection ID: {inspection.id} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Generated: {datetime.utcnow().strftime('%d %b %Y, %H:%M UTC')} &nbsp;&nbsp;|&nbsp;&nbsp; "
            f"Rule Version: {inspection.rule_version}",
            STYLES["LLSub"],
        )
    )

    meta_rows = [
        ["Product", inspection.product_name, "Brand", inspection.brand],
        ["Category", inspection.category, "Location", inspection.location or "—"],
        ["Inspector", inspection.inspector_name, "Role", inspection.inspector_role],
        ["Date/Time", inspection.created_at.strftime("%d %b %Y, %H:%M"), "Status", inspection.status.replace("_", " ")],
    ]
    meta_table = Table(meta_rows, colWidths=[70 * mm / 2, 130 * mm / 2, 60 * mm / 2, 130 * mm / 2])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#5B6470")),
                ("TEXTCOLOR", (2, 0), (2, -1), colors.HexColor("#5B6470")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D8D2C4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 10))

    if inspection.source_type == "ECOMMERCE_LISTING":
        story.append(Paragraph(f"Source: E-Commerce Listing — {inspection.source_url}", STYLES["LLSub"]))

    status_color = STATUS_COLORS.get(inspection.status, colors.grey)
    status_style = ParagraphStyle(
        name="Status", fontSize=14, textColor=status_color, spaceAfter=10, spaceBefore=4,
    )
    story.append(Paragraph(f"Final Compliance Status: {inspection.status.replace('_', ' ')}", status_style))

    if inspection.barcode_raw_value:
        story.append(
            Paragraph(
                f"Barcode: {inspection.barcode_raw_value} ({inspection.barcode_symbology}) — "
                f"{inspection.barcode_registry_match.replace('_', ' ')}. {inspection.barcode_note}",
                STYLES["Normal"],
            )
        )

    story.append(Paragraph("Mandatory Declarations", STYLES["LLSection"]))
    story.append(_declaration_table(inspection.declarations))

    story.append(Paragraph("Rule Compliance Findings", STYLES["LLSection"]))
    story.append(_rule_table(inspection.rule_results))

    if inspection.images:
        story.append(Paragraph("Photographic Evidence", STYLES["LLSection"]))
        for img in inspection.images[:4]:  # keep the PDF a reasonable size; full set stays in object storage
            try:
                image_bytes = storage_service.get_object(img.storage_key)
                rl_image = RLImage(io.BytesIO(image_bytes), width=70 * mm, height=52 * mm)
                story.append(Paragraph(f"{img.slot.title()}", STYLES["Normal"]))
                story.append(rl_image)
                story.append(Spacer(1, 6))
            except Exception:
                story.append(Paragraph(f"{img.slot.title()}: image unavailable in storage.", STYLES["Normal"]))

    if inspection.notes:
        story.append(Paragraph("Inspector Remarks", STYLES["LLSection"]))
        story.append(Paragraph(inspection.notes, STYLES["Normal"]))

    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            "This report was generated with AI-assisted OCR and rule-based analysis. Findings marked "
            "REVIEW require human verification before being treated as conclusive. All manual "
            "verification actions are recorded in the audit log.",
            STYLES["LLSub"],
        )
    )

    doc.build(story)
    return buffer.getvalue()
