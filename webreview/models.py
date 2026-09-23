"""Data model for the Django wrapper around contract_reviewer.

Mirrors Specifications.md §4, which maps onto Contracts Database Plan.md's original
schema and fills the gaps ARCHITECTURE.md §6/§7 flagged (a real verification ledger and
run/agent history, and execution_status kept separate from report_status).
"""
from __future__ import annotations

from django.db import models


def contract_document_upload_path(instance: "ContractDocument", filename: str) -> str:
    return f"contracts/{instance.contract_id}/{filename}"


def review_pdf_upload_path(instance: "Review", filename: str) -> str:
    return f"reviews/{instance.id}/{filename}"


def summary_pdf_upload_path(instance: "Summary", filename: str) -> str:
    return f"summaries/{instance.id}/{filename}"


class Contract(models.Model):
    title = models.CharField(max_length=255)
    contract_type = models.CharField(max_length=100, blank=True)
    client_role = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.title


class ContractDocument(models.Model):
    EXTRACTION_PENDING = "pending"
    EXTRACTION_COMPLETED = "completed"
    EXTRACTION_FAILED = "failed"
    EXTRACTION_STATUS_CHOICES = [
        (EXTRACTION_PENDING, "Pending"),
        (EXTRACTION_COMPLETED, "Completed"),
        (EXTRACTION_FAILED, "Failed"),
    ]

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="documents")
    version_number = models.PositiveIntegerField(default=1)
    original_filename = models.CharField(max_length=255)
    file_extension = models.CharField(max_length=10)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size_bytes = models.PositiveBigIntegerField()
    file = models.FileField(upload_to=contract_document_upload_path)
    file_hash_sha256 = models.CharField(max_length=64)
    is_current = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    extraction_status = models.CharField(
        max_length=20, choices=EXTRACTION_STATUS_CHOICES, default=EXTRACTION_PENDING
    )
    extraction_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "version_number"], name="unique_contract_version"
            )
        ]

    def __str__(self) -> str:
        return f"{self.original_filename} (v{self.version_number})"


class Review(models.Model):
    # Execution state -- distinct from report_status below, per the workflow's hard rule.
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXECUTION_STATUS_CHOICES = [
        (PENDING, "Pending"),
        (RUNNING, "Running"),
        (SUCCEEDED, "Succeeded"),
        (FAILED, "Failed"),
    ]

    # Report release status, set by reconcile/assemble -- see Workflow/SKILL.md Stage 4.
    COMPLETED = "Completed"
    PROVISIONAL = "Provisional"
    INCOMPLETE = "Incomplete"
    REPORT_STATUS_CHOICES = [
        (COMPLETED, "Completed"),
        (PROVISIONAL, "Provisional"),
        (INCOMPLETE, "Incomplete"),
    ]

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="reviews")
    document = models.ForeignKey(ContractDocument, on_delete=models.PROTECT, related_name="reviews")
    run_id = models.CharField(max_length=64, unique=True)
    client_perspective = models.TextField(blank=True)
    research_date = models.DateField(null=True, blank=True)
    max_cycles = models.PositiveIntegerField(default=2)

    execution_status = models.CharField(
        max_length=20, choices=EXECUTION_STATUS_CHOICES, default=PENDING
    )
    report_status = models.CharField(
        max_length=20, choices=REPORT_STATUS_CHOICES, blank=True
    )
    commercial_recommendation = models.CharField(max_length=100, blank=True)
    correction_cycle = models.PositiveIntegerField(default=0)
    current_stage_label = models.CharField(max_length=100, blank=True)
    progress_percent = models.PositiveIntegerField(default=0)

    report_markdown = models.TextField(blank=True)
    report_context = models.JSONField(null=True, blank=True)
    report_pdf = models.FileField(upload_to=review_pdf_upload_path, null=True, blank=True)
    incomplete_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # refreshes on every save -- used for stall detection
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Review {self.run_id} ({self.execution_status})"


class Finding(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="findings")
    finding_id = models.CharField(max_length=20)
    severity = models.CharField(max_length=20)
    confidence = models.CharField(max_length=20)
    clause_reference = models.CharField(max_length=255, blank=True)
    clause_text = models.TextField(blank=True)
    affected_party = models.CharField(max_length=255, blank=True)
    trigger_scenario = models.TextField(blank=True)
    consequence = models.TextField(blank=True)
    legal_proposition = models.TextField(blank=True)
    rating_rationale = models.TextField(blank=True)
    recommended_amendment = models.TextField(blank=True)
    fallback_position = models.TextField(blank=True)
    residual_risk = models.TextField(blank=True)
    missing_evidence = models.TextField(blank=True)
    counterargument = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="open")

    class Meta:
        ordering = ["finding_id"]
        constraints = [
            models.UniqueConstraint(fields=["review", "finding_id"], name="unique_review_finding")
        ]

    def __str__(self) -> str:
        return f"{self.finding_id} ({self.severity})"


class Authority(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="authorities")
    authority_id = models.CharField(max_length=20)
    authority_type = models.CharField(max_length=20)
    title = models.CharField(max_length=500)
    citation = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=1000, blank=True)
    pinpoint = models.CharField(max_length=255, blank=True)
    application_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["authority_id"]
        constraints = [
            models.UniqueConstraint(fields=["review", "authority_id"], name="unique_review_authority")
        ]
        verbose_name_plural = "authorities"

    def __str__(self) -> str:
        return f"{self.authority_id} ({self.authority_type})"


class VerificationRecord(models.Model):
    """One row per finding-authority-proposition relationship -- never deduped to one
    row per authority, per Workflow/SKILL.md Stage 3."""

    finding = models.ForeignKey(Finding, on_delete=models.CASCADE, related_name="verification_records")
    authority = models.ForeignKey(Authority, on_delete=models.CASCADE, related_name="verification_records")
    proposition_checked = models.TextField()
    status = models.CharField(max_length=20)  # Verified | Qualified | Unsupported | Unverified
    identity_check = models.TextField(blank=True)
    text_check = models.TextField(blank=True)
    attribution_check = models.TextField(blank=True)
    proposition_check = models.TextField(blank=True)
    treatment_check = models.TextField(blank=True)
    application_check = models.TextField(blank=True)
    caveats = models.TextField(blank=True)

    def __str__(self) -> str:
        return f"{self.finding.finding_id}/{self.authority.authority_id}: {self.status}"


class Summary(models.Model):
    """A plain-English contract summary run -- deliberately a separate model from Review,
    not Review + a discriminator field, since none of Review's findings/authorities/
    severity/report_status/correction-cycle concepts apply here (Specifications.md §12)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXECUTION_STATUS_CHOICES = [
        (PENDING, "Pending"),
        (RUNNING, "Running"),
        (SUCCEEDED, "Succeeded"),
        (FAILED, "Failed"),
    ]

    contract = models.ForeignKey(Contract, on_delete=models.CASCADE, related_name="summaries")
    document = models.ForeignKey(ContractDocument, on_delete=models.PROTECT, related_name="summaries")
    run_id = models.CharField(max_length=64, unique=True)

    execution_status = models.CharField(max_length=20, choices=EXECUTION_STATUS_CHOICES, default=PENDING)
    current_stage_label = models.CharField(max_length=100, blank=True)
    progress_percent = models.PositiveIntegerField(default=0)

    summary_context = models.JSONField(null=True, blank=True)
    summary_pdf = models.FileField(upload_to=summary_pdf_upload_path, null=True, blank=True)
    fidelity_issues = models.JSONField(default=list, blank=True)
    incomplete_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # refreshes on every save -- used for stall detection
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "summaries"

    def __str__(self) -> str:
        return f"Summary {self.run_id} ({self.execution_status})"


class RunEvent(models.Model):
    """Run/agent history: one row per stage transition and per model call, satisfying
    TECHNICAL HANDOVER.md's 'record actual provider/model/tier/effort' requirement."""

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="events")
    stage = models.CharField(max_length=50)
    role = models.CharField(max_length=50, blank=True)
    tier = models.CharField(max_length=20, blank=True)
    provider = models.CharField(max_length=20, blank=True)
    model = models.CharField(max_length=100, blank=True)
    effort_actual = models.CharField(max_length=50, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    detail = models.TextField(blank=True)

    class Meta:
        ordering = ["occurred_at"]

    def __str__(self) -> str:
        return f"{self.stage} @ {self.occurred_at:%H:%M:%S}"
