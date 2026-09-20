"""CAPA closure report PDF (ReportLab) rendered from the same ClosureEvidence bundle as the JSON."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from schemas import ClosureEvidence, FishboneEntry, WhyStep

TITLE = "CAPA Closure Report — 21 CFR 820.100"
CFR_SUMMARY = (
    "21 CFR 820.100(a) requires procedures for corrective and preventive action that include: "
    "(1) analyzing processes, work operations, quality records, complaints and other quality "
    "data to identify existing and potential causes of nonconforming product; (2) investigating "
    "the cause of nonconformities relating to product, processes and the quality system; "
    "(3) identifying the action(s) needed to correct and prevent recurrence; (4) verifying or "
    "validating the corrective and preventive action to ensure it is effective and does not "
    "adversely affect the finished device; (5) implementing and recording changes in methods "
    "and procedures; (6) ensuring that information related to quality problems or nonconforming "
    "product is disseminated to those directly responsible for assuring quality; and "
    "(7) submitting relevant information on identified quality problems and CAPA for "
    "management review. Under 820.100(b), all activities required under this section, and "
    "their results, shall be documented. This report is that documentation; the root cause and "
    "effectiveness determinations recorded here are human quality-engineering judgments."
)
_GRID = TableStyle(
    [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
)


def _rows(bundle: ClosureEvidence) -> tuple[list[str], list[list[str]]]:
    """RCA steps as a table: the 5-why chain or the fishbone entries."""
    if bundle.rca.method == "5-why":
        why = [s for s in bundle.rca.steps if isinstance(s, WhyStep)]
        return ["#", "Question", "Answer"], [
            [str(i), s.question, s.answer] for i, s in enumerate(why, 1)
        ]
    fish = [s for s in bundle.rca.steps if isinstance(s, FishboneEntry)]
    return ["Category", "Cause"], [[s.category.value, s.cause] for s in fish]


def render_closure_report(bundle: ClosureEvidence, out: Path) -> Path:
    nc, rca, capa, chk, cl = (
        bundle.nonconformance,
        bundle.rca,
        bundle.capa,
        bundle.effectiveness_check,
        bundle.closure,
    )
    styles = getSampleStyleSheet()
    body, h1, h2 = styles["BodyText"], styles["Heading1"], styles["Heading2"]

    def para(text: str) -> Paragraph:
        return Paragraph(escape(text), body)

    def kv(pairs: list[tuple[str, str]]) -> Table:
        return Table([[para(k), para(v)] for k, v in pairs], style=_GRID, hAlign="LEFT")

    header, rows = _rows(bundle)
    band = rca.confidence_band.value if rca.confidence_band else "n/a"
    category = rca.suggested_category.value if rca.suggested_category else "none"
    confidence = "n/a" if rca.confidence is None else f"{rca.confidence:.2f}"
    story: list[object] = [
        Paragraph(escape(TITLE), h1),
        para(f"Evidence {bundle.evidence_id} generated {bundle.generated_at.isoformat()}"),
        Paragraph("Nonconformance", h2),
        kv(
            [
                ("ID", nc.id),
                ("Source", nc.source),
                ("Severity", nc.severity),
                ("Detected", nc.detected_date.isoformat()),
                ("Status", nc.status.value),
                ("Description", nc.description),
            ]
        ),
        Paragraph("Root Cause Analysis", h2),
        para(f"Method: {rca.method}"),
        Table(
            [[para(c) for c in header], *[[para(c) for c in r] for r in rows]],
            style=_GRID,
            hAlign="LEFT",
        ),
        para(
            f"Explainer suggestion: {category} (confidence {confidence}, band {band}); "
            "the suggestion is advisory only"
        ),
        para(f"Root cause (human-entered): {rca.root_cause_text or 'not recorded'}"),
        Paragraph("Corrective Action", h2),
        kv(
            [
                ("ID", capa.id),
                ("Description", capa.action_description),
                ("Owner", capa.owner),
                ("Due", capa.due_date.isoformat()),
                ("Status", capa.status),
            ]
        ),
        Paragraph("Effectiveness Verification", h2),
        kv(
            [
                ("Date", chk.check_date.isoformat()),
                ("Method", chk.method),
                ("Result", chk.result),
                ("Evidence URI", chk.evidence_uri or "none"),
            ]
        ),
        Paragraph("Closure", h2),
        kv(
            [
                ("Closed", cl.closed_date.isoformat()),
                ("Closed by", cl.closed_by),
                ("Linked requirements", ", ".join(cl.linked_requirement_ids) or "none"),
            ]
        ),
        Paragraph("Regulatory Basis", h2),
        para(CFR_SUMMARY),
    ]
    flow: list[object] = []
    for item in story:
        flow += [item, Spacer(1, 6)]
    out.parent.mkdir(parents=True, exist_ok=True)
    # ponytail: pageCompression=0 keeps text objects greppable so tests (and humans) can assert
    # on the raw bytes without a PDF parser; flip to 1 if file size ever matters.
    SimpleDocTemplate(str(out), title=TITLE, pageCompression=0).build(flow)
    return out
