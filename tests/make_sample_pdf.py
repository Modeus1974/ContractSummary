"""Builds a short synthetic tenancy contract PDF for manual end-to-end testing."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

CLAUSES = [
    "TENANCY AGREEMENT",
    "",
    "This Tenancy Agreement is made between ABC Pte Ltd (Landlord) and Jane Tan (Tenant)",
    "for the premises at 123 Example Road, Singapore.",
    "",
    "1. Term. The tenancy shall be for a fixed term of 12 months commencing 1 January 2026.",
    "",
    "2. Rent. The Tenant shall pay monthly rent of S$3,500, payable in advance on the 1st",
    "of each month.",
    "",
    "3. Security Deposit. The Tenant shall pay a security deposit of S$10,500 (three months'",
    "rent) upon signing. The Landlord may deduct from the deposit for any damage beyond",
    "fair wear and tear.",
    "",
    "4. Early Termination. Should the Tenant terminate this Agreement before the end of the",
    "fixed term for any reason, the Tenant forfeits the entire security deposit with no right",
    "of appeal, regardless of the reason for termination.",
    "",
    "5. Repairs. The Tenant shall bear the full cost of all repairs to the premises during the",
    "tenancy, including structural repairs and repairs arising from fair wear and tear.",
    "",
    "6. Diplomatic Clause. There is no diplomatic clause; the Tenant has no right to terminate",
    "early even in the event of posting overseas by the Tenant's employer.",
    "",
    "7. Governing Law. This Agreement is governed by the laws of Singapore.",
]


def build(path: Path = FIXTURES_DIR / "sample_tenancy.pdf") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in CLAUSES:
        page.insert_text((72, y), line, fontsize=11)
        y += 16
        if y > 760:
            page = doc.new_page()
            y = 72
    doc.save(path)
    doc.close()
    return path


if __name__ == "__main__":
    out = build()
    print(f"Wrote {out}")
