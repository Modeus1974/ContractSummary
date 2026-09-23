"""Extracts page-numbered text from a contract PDF, flagging likely-scanned pages.

The source PDF is treated as immutable evidence: this module only reads it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf as fitz


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_pdf(path: Path) -> dict:
    """Returns {ok, text, pages, warnings, scanned_pages}. Never raises on a bad/corrupt PDF;
    extraction failure is reported in the result so the caller can route to the Incomplete path.
    """
    result = {
        "ok": False,
        "text": "",
        "pages": [],
        "warnings": [],
        "scanned_pages": [],
    }
    try:
        doc = fitz.open(path)
    except Exception as exc:  # corrupt / encrypted / not a PDF
        result["warnings"].append(f"Could not open PDF: {exc}")
        return result

    if doc.is_encrypted:
        result["warnings"].append(
            "PDF is encrypted/password-protected; cannot extract text."
        )
        doc.close()
        return result

    pages = []
    scanned_pages = []
    for page_index in range(doc.page_count):
        page = doc[page_index]
        page_no = page_index + 1
        text = page.get_text().strip()
        if not text and page.get_images():
            scanned_pages.append(page_no)
            result["warnings"].append(
                f"Page {page_no} has no extractable text layer but contains images "
                "(likely scanned); OCR is out of scope, marked as unreviewed."
            )
        pages.append({"page_no": page_no, "text": text})
    doc.close()

    combined_text = "\n\n".join(
        f"[Page {p['page_no']}]\n{p['text']}" for p in pages if p["text"]
    )

    result["pages"] = pages
    result["scanned_pages"] = scanned_pages
    result["text"] = combined_text
    result["ok"] = bool(combined_text.strip())
    if not result["ok"]:
        result["warnings"].append("No extractable text found anywhere in the document.")
    return result
