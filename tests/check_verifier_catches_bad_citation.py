"""Manual check: does the independent verifier catch a deliberately fabricated citation?

Calls contract_reviewer.nodes.verify directly against a hand-crafted state. This makes
real Anthropic + Tavily API calls (small cost) -- run it deliberately, not in a loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contract_reviewer import config, runtime  # noqa: E402
from contract_reviewer.nodes.verify import verify_node  # noqa: E402

FAKE_STATE = {
    "extraction": {
        "text": "[Page 1]\n4. Early Termination. Should the Tenant terminate this Agreement before "
        "the end of the fixed term for any reason, the Tenant forfeits the entire security deposit "
        "with no right of appeal, regardless of the reason for termination."
    },
    "selected_skill_texts": {},
    "draft_findings": [
        {
            "finding_id": "F001",
            "clause_reference": "Clause 4",
            "clause_text": "the Tenant forfeits the entire security deposit with no right of appeal",
            "affected_party": "Tenant",
            "trigger_scenario": "Tenant terminates early for any reason",
            "consequence": "Total loss of a 3-month deposit regardless of circumstances",
            "severity": "High",
            "confidence": "High",
            "rating_rationale": "Total forfeiture with no proportionality is a severe one-sided term",
            "legal_proposition": "Singapore courts will strike down a forfeiture clause that "
            "operates as an unconscionable penalty rather than a genuine pre-estimate of loss",
            "authority_ids": ["A001"],
            "recommended_amendment": "Cap forfeiture at actual loss suffered",
            "fallback_position": "Pro-rate forfeiture by month",
            "residual_risk": "None if amended",
        }
    ],
    "authority_ledger": [
        {
            "authority_id": "A001",
            "authority_type": "case",
            "title": "Made-Up Pte Ltd v Nonexistent Holdings Pte Ltd",
            "citation": "[2099] SGCA 999",
            "url": None,
            "pinpoint": "[42]",
            "application_notes": "Fabricated case, does not exist -- this is the deliberate defect "
            "this script is checking the verifier catches.",
        }
    ],
}


def main() -> int:
    config.load_env()
    runtime.set_tiers(config.load_tier_config())

    result = verify_node(FAKE_STATE)
    records = result["verification_records"]
    print(f"Verification records returned: {len(records)}")
    for r in records:
        print(
            f"  {r['finding_id']} / {r['authority_id']}: {r['status']} -- {r['identity_check']}"
        )

    bad = [r for r in records if r["authority_id"] == "A001"]
    if not bad:
        print("FAIL: no verification record produced for the fabricated authority")
        return 1
    status = bad[0]["status"]
    if status in ("Unsupported", "Unverified"):
        print(f"PASS: fabricated citation correctly flagged as {status}")
        return 0
    print(
        f"FAIL: fabricated citation was rated {status}, expected Unsupported or Unverified"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
