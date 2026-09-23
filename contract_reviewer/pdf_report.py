"""Renders the same report data used for the Markdown report into a styled PDF."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"

# xhtml2pdf's default fonts only cover WinAnsiEncoding. LLM-generated prose sometimes
# uses characters outside that (e.g. a filled-circle placeholder bullet, arrows), which
# would otherwise render as a blank box. Map the common offenders to safe equivalents.
# Public (no leading underscore) since summary_pdf_report.py reuses this too.
GLYPH_FALLBACKS = {
    "●": "•",  # ● -> •
    "○": "o",  # ○
    "▪": "-",  # ▪
    "→": "->",  # →
    "←": "<-",  # ←
    "↔": "<->",  # ↔
    "✓": "Yes",  # ✓
    "✗": "No",  # ✗
    "✘": "No",  # ✘
}


def sanitize_glyphs(html: str) -> str:
    for bad, good in GLYPH_FALLBACKS.items():
        html = html.replace(bad, good)
    return html


def render_pdf(context: dict) -> bytes:
    """Renders templates/report.pdf.html.jinja with `context` (the same kwargs used for
    the Markdown template) and converts it to PDF bytes. Raises on failure -- the caller
    decides how to handle a PDF-generation failure without affecting the Markdown report,
    which remains the authoritative artifact."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("report.pdf.html.jinja")
    html = sanitize_glyphs(template.render(**context))

    buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=buffer)
    if result.err:
        raise RuntimeError(
            f"xhtml2pdf reported {result.err} error(s) while rendering the PDF"
        )
    return buffer.getvalue()
