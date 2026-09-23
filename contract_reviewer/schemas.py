"""Pydantic schemas exchanged at node boundaries (LLM structured output <-> dict state)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["Critical", "High", "Medium", "Low"]
Confidence = Literal["High", "Medium", "Low"]
AuthorityStatus = Literal["Verified", "Qualified", "Unsupported", "Unverified"]
ReportStatus = Literal["Completed", "Provisional", "Incomplete"]
Recommendation = Literal[
    "proceed", "proceed subject to changes", "resolve blockers first"
]


class RoutingRecord(BaseModel):
    contract_type: str = Field(description="Identified substance of the agreement")
    substantive_indicators: list[str] = Field(
        description="Clause-referenced evidence supporting the classification"
    )
    selected_skill_paths: list[str] = Field(
        description="Relative paths under 'Contract Skills/' selected for this contract, e.g. "
        "'Contract Skills/Tenancy Agreement.md'"
    )
    scope_per_skill: dict[str, str] = Field(
        default_factory=dict,
        description="What each selected skill covers, for mixed agreements",
    )
    confidence: Confidence
    rejected_alternatives: list[str] = Field(default_factory=list)
    unresolved_facts: list[str] = Field(default_factory=list)


class Authority(BaseModel):
    authority_id: str = Field(description="Stable ID, e.g. 'A001'")
    authority_type: Literal["statute", "case", "regulation", "guidance"]
    title: str
    citation: str | None = None
    url: str | None = None
    pinpoint: str = Field(description="Section, subsection, or judgment paragraph")
    application_notes: str = Field(
        description="How this authority applies to the finding"
    )


class Finding(BaseModel):
    finding_id: str = Field(description="Stable ID, e.g. 'F001'")
    clause_reference: str
    clause_text: str = Field(
        description="Short accurate quotation or identified omission"
    )
    affected_party: str
    trigger_scenario: str
    consequence: str
    severity: Severity
    confidence: Confidence
    rating_rationale: str
    legal_proposition: str
    authority_ids: list[str] = Field(default_factory=list)
    recommended_amendment: str
    fallback_position: str
    residual_risk: str
    missing_evidence: str | None = None
    counterargument: str | None = None
    status: Literal["open", "amended", "resolved"] = "open"


class ReviewDraft(BaseModel):
    findings: list[Finding]
    authorities: list[Authority]
    documents_and_issue_areas_considered: list[str] = Field(default_factory=list)
    areas_with_no_material_finding: list[str] = Field(default_factory=list)


class VerificationRecord(BaseModel):
    finding_id: str
    authority_id: str
    proposition_checked: str
    status: AuthorityStatus
    identity_check: str
    text_check: str
    attribution_check: str
    proposition_check: str
    treatment_check: str = Field(
        description="Search date, terms/sources and limits; "
        "'no adverse treatment found in the sources searched', never 'guaranteed good law'"
    )
    application_check: str
    caveats: str | None = None


class VerificationDraft(BaseModel):
    verification_records: list[VerificationRecord]
    newly_identified_findings: list[Finding] = Field(
        default_factory=list,
        description="Material omitted risks the verifier spotted; these are NOT auto-approved, "
        "reconcile must route them back through review before inclusion",
    )
    unsupported_assertions_in_summary: list[str] = Field(default_factory=list)


class FactualCheckNote(BaseModel):
    finding_id: str | None = None
    category: Literal[
        "quotation", "coverage", "duplicate", "severity_ordering", "consistency"
    ]
    description: str
    confirmed: bool


class CorrectionLogEntry(BaseModel):
    cycle: int
    defect_description: str
    linked_finding_id: str | None
    resolution: Literal["amended", "removed", "unresolved"]


class ExecutiveAssessment(BaseModel):
    paragraph: str = Field(
        description="Conditional recommendation and the largest risks, including unresolved "
        "potential blockers -- built only from the supplied approved data"
    )


class ContractParty(BaseModel):
    name: str
    role: str = Field(description="e.g. landlord, tenant, employer, buyer, seller")


class PartyObligations(BaseModel):
    party: str
    obligations: list[str]


class KeyDate(BaseModel):
    date: str = Field(description="Quoted as it appears in the source, e.g. '1 January 2026'")
    description: str


class ContractSummary(BaseModel):
    """Structured output for the Contract Summary skill (kind: task) -- descriptive,
    not evaluative. Mirrors Contract Skills/Contract Summary.md's required sections
    one-to-one so docx_report.py can render each section deterministically."""

    contract_type: str
    parties: list[ContractParty]
    effective_date: str = Field(description="Short value only, e.g. '1 January 2026' -- no citations or commentary")
    term_duration: str = Field(description="Short value only, e.g. '12 months' -- no citations or commentary")
    governing_law: str
    dispute_resolution: str
    key_monetary_value: str = Field(
        description="Short value only, e.g. 'S$3,500/month rent; S$10,500 deposit' -- no clause "
        "citations or commentary here; put context in subject_matter_summary or payment_terms instead"
    )
    subject_matter_summary: str = Field(description="One paragraph, plain English")
    obligations_by_party: list[PartyObligations]
    payment_terms: str
    key_dates: list[KeyDate] = Field(default_factory=list)
    termination_and_exit: str
    liability_snapshot: str
    ip_confidentiality_data: str | None = Field(
        default=None, description="Omit (leave null) if the contract has nothing on this"
    )
    notable_or_unusual_terms: list[str] = Field(
        default_factory=list, description="At most ~5 items, per the skill's own discipline"
    )
    missing_information: list[str] = Field(default_factory=list)


class ModelAssignment(BaseModel):
    role: str
    tier: str
    provider: str
    model: str
    effort_requested: str | None = None
    effort_actual: str = "not exposed"
