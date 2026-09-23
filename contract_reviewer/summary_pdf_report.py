"""Renders a ContractSummary into a styled PDF, mirroring pdf_report.py's approach
(same Jinja2 -> xhtml2pdf pipeline, same glyph sanitization) for the web app's download
button. The CLI's summarise.py keeps using docx_report.py for Word output -- see
Specifications.md §12 for why both formats exist rather than one replacing the other.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from xhtml2pdf import pisa

from contract_reviewer.pdf_report import sanitize_glyphs
from contract_reviewer.schemas import ContractSummary

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def render_pdf(summary: ContractSummary, context: dict) -> bytes:
    """Renders templates/summary.pdf.html.jinja from `summary` plus `context` (source_filename,
    source_sha256, client_role, generated_at, fidelity_issues) and converts to PDF bytes."""
    env = Environment(loader=FileSystemLoader(str(_TEMPLATE_DIR)))
    template = env.get_template("summary.pdf.html.jinja")
    html = sanitize_glyphs(template.render(summary=summary, **context))

    buffer = BytesIO()
    result = pisa.CreatePDF(html, dest=buffer)
    if result.err:
        raise RuntimeError(f"xhtml2pdf reported {result.err} error(s) while rendering the PDF")
    return buffer.getvalue()
