# -*- coding: utf-8 -*-
"""Plain-text and PDF report rendering."""
import datetime

from fpdf import FPDF

# Max width (px) the embedded photo is downscaled to before being placed in
# the PDF -- this is a report-only thumbnail, independent of whatever
# resolution the analysis itself was run against, so the PDF stays small.
_PDF_IMAGE_MAX_DIM = 500

# Brand-ish colors, loosely matched to dermatica.styles so the PDF doesn't
# feel disconnected from the app (kept local/simple -- styles.py's dicts are
# CSS-string oriented (rgba(...) strings, hex), not the RGB tuples FPDF wants).
_NAVY   = (27, 50, 82)      # styles.BRAND["navy"] == #1B3252
_GOLD   = (184, 136, 42)    # styles.BRAND["gold"] == #B8882A
_DANGER = (139, 42, 42)     # styles.SEMANTIC["danger"] == #8B2A2A
_INK    = (26, 25, 24)
_MUTED  = (90, 88, 85)


def build_report(analysis: dict, filename: str) -> str:
    now   = datetime.datetime.now().strftime("%B %d, %Y at %H:%M")
    conds = "\n".join(
        f"  [{c['level']:6}] {c['name']}\n          {c.get('description','')}"
        for c in analysis.get("conditions", [])
    )
    rfs  = "\n".join(f"  - {r}" for r in analysis.get("risk_factors", []))
    wtsd = "\n".join(f"  - {s}" for s in analysis.get("when_to_see_doctor", []))
    sct  = "\n".join(f"  - {t}" for t in analysis.get("self_care_tips", []))
    return f"""
DERMAI PRO -- SKIN ANALYSIS REPORT
=====================================

Generated : {now}
File      : {filename}

-------------------------------------
SEVERITY ASSESSMENT
  Level : {analysis.get('severity_level','N/A')}
  Score : {analysis.get('severity_score','N/A')}/10

-------------------------------------
VISUAL OBSERVATIONS
{analysis.get('visual_description','N/A')}

-------------------------------------
POSSIBLE CONDITIONS
{conds or '  N/A'}

-------------------------------------
RISK FACTORS
{rfs or '  N/A'}

-------------------------------------
RECOMMENDED ACTION : {analysis.get('recommended_action','N/A').replace('_',' ')}
{analysis.get('action_detail','')}

-------------------------------------
WHEN TO SEEK MEDICAL ATTENTION
{wtsd or '  N/A'}

-------------------------------------
SELF-CARE RECOMMENDATIONS
{sct or '  N/A'}

-------------------------------------
MEDICAL DISCLAIMER
This report is AI-generated for informational purposes only.
It does NOT constitute a medical diagnosis or treatment advice.
Always consult a licensed dermatologist or healthcare provider.

-------------------------------------
Dermatica | Powered by Groq & Llama AI
"""


def _downscale_for_pdf(image):
    """Return a copy of `image` downscaled so its longest side is at most
    _PDF_IMAGE_MAX_DIM px. The report only needs a thumbnail-sized photo,
    not the full analysis-resolution image, to keep the PDF small."""
    img = image.copy()
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    longest = max(w, h)
    if longest > _PDF_IMAGE_MAX_DIM:
        scale = _PDF_IMAGE_MAX_DIM / float(longest)
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    return img


def _pdf_section_heading(pdf: FPDF, text: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_NAVY)
    pdf.ln(3)
    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*_GOLD)
    pdf.set_line_width(0.5)
    y = pdf.get_y()
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(2)
    pdf.set_text_color(*_INK)


def _pdf_body_text(pdf: FPDF, text: str, size: int = 10, style: str = "") -> None:
    pdf.set_font("Helvetica", style, size)
    pdf.multi_cell(0, 5.5, text, new_x="LMARGIN", new_y="NEXT")


def _pdf_bulleted_list(pdf: FPDF, items: list, empty_text: str = "None noted.") -> None:
    pdf.set_font("Helvetica", "", 10)
    if not items:
        pdf.set_text_color(*_MUTED)
        pdf.multi_cell(0, 5.5, empty_text, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(*_INK)
        return
    for item in items:
        # Use multi_cell (not cell) so long entries wrap instead of clipping.
        # new_x="LMARGIN" is essential here: multi_cell's default leaves the
        # cursor at the right margin, which would shrink available width to
        # zero on the next call and raise FPDFException.
        pdf.multi_cell(0, 5.5, f"-  {item}", new_x="LMARGIN", new_y="NEXT")


def build_pdf_report(analysis: dict, image, filename: str) -> bytes:
    """Render the same analysis dict consumed by build_report() as a PDF,
    with the uploaded photo embedded. Returns raw PDF bytes suitable for a
    Streamlit download_button."""
    now = datetime.datetime.now().strftime("%B %d, %Y at %H:%M")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # ── Title ───────────────────────────────
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*_NAVY)
    pdf.cell(0, 10, "Dermatica Analysis Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*_MUTED)
    pdf.cell(0, 5, f"Generated: {now}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"File: {filename}", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*_INK)
    pdf.ln(2)

    # ── Embedded photo ──────────────────────
    if image is not None:
        try:
            thumb = _downscale_for_pdf(image)
            _pdf_section_heading(pdf, "Analyzed Image")
            # Constrain placement width on the page; fpdf2 accepts a Pillow
            # Image object directly for `name` in this version (no need to
            # round-trip through a BytesIO buffer).
            pdf.image(thumb, w=80)
            pdf.ln(2)
        except Exception:
            # Never let a thumbnailing/embedding hiccup break report
            # generation -- the rest of the report still has value without it.
            pass

    # ── Severity ─────────────────────────────
    _pdf_section_heading(pdf, "Severity Assessment")
    sev_level = analysis.get("severity_level") or "N/A"
    sev_score = analysis.get("severity_score", "N/A")
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"Level: {sev_level}    Score: {sev_score}/10", new_x="LMARGIN", new_y="NEXT")

    # ── Visual description ───────────────────
    vd = (analysis.get("visual_description") or "").strip()
    if vd:
        _pdf_section_heading(pdf, "Visual Observations")
        _pdf_body_text(pdf, vd)

    # ── Conditions ────────────────────────────
    _pdf_section_heading(pdf, "Possible Conditions")
    conditions = analysis.get("conditions") or []
    if not conditions:
        pdf.set_text_color(*_MUTED)
        _pdf_body_text(pdf, "None noted.")
        pdf.set_text_color(*_INK)
    else:
        for c in conditions:
            name  = c.get("name", "Unknown")
            level = c.get("level", "")
            desc  = (c.get("description") or "").strip()
            header = f"{name}" + (f"  [{level}]" if level else "")
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 5.5, header, new_x="LMARGIN", new_y="NEXT")
            if desc:
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(*_MUTED)
                pdf.multi_cell(0, 5.5, desc, new_x="LMARGIN", new_y="NEXT")
                pdf.set_text_color(*_INK)
            pdf.ln(1)

    # ── Risk factors ──────────────────────────
    _pdf_section_heading(pdf, "Risk Factors")
    _pdf_bulleted_list(pdf, analysis.get("risk_factors") or [])

    # ── Recommended action ────────────────────
    _pdf_section_heading(pdf, "Recommended Action")
    action = (analysis.get("recommended_action") or "N/A").replace("_", " ")
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(0, 6, action, new_x="LMARGIN", new_y="NEXT")
    detail = (analysis.get("action_detail") or "").strip()
    if detail:
        pdf.set_font("Helvetica", "", 10)
        _pdf_body_text(pdf, detail)

    # ── When to see a doctor ──────────────────
    _pdf_section_heading(pdf, "When to Seek Medical Attention")
    _pdf_bulleted_list(pdf, analysis.get("when_to_see_doctor") or [])

    # ── Self-care tips ─────────────────────────
    _pdf_section_heading(pdf, "Self-Care Recommendations")
    _pdf_bulleted_list(pdf, analysis.get("self_care_tips") or [])

    # ── Disclaimer (unmistakable: bold + boxed) ─
    pdf.ln(4)
    pdf.set_fill_color(*_DANGER)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 10)
    pdf.multi_cell(
        0, 6,
        "MEDICAL DISCLAIMER: This report is AI-generated for informational "
        "purposes only. It does NOT constitute a medical diagnosis or "
        "treatment advice. Always consult a licensed dermatologist or "
        "healthcare provider.",
        fill=True,
        border=1,
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.set_text_color(*_INK)

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*_MUTED)
    pdf.ln(3)
    pdf.cell(0, 5, "Dermatica | Powered by Groq & Llama AI", new_x="LMARGIN", new_y="NEXT")

    out = pdf.output()
    return bytes(out)
