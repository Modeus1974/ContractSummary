from __future__ import annotations

import hashlib
import logging

from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django_q.tasks import async_task

from contract_reviewer import io_utils
from webreview import stall
from webreview.forms import ContractUploadForm
from webreview.models import Contract, ContractDocument, Summary

logger = logging.getLogger("webreview")


def _hash_uploaded_file(uploaded_file) -> str:
    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    return digest.hexdigest()


def upload_view(request):
    if request.method == "POST":
        form = ContractUploadForm(request.POST, request.FILES)
        if form.is_valid():
            uploaded = form.cleaned_data["file"]
            title = form.cleaned_data["title"] or uploaded.name
            client_role = form.cleaned_data["client_role"]
            suffix = "." + uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""

            contract = Contract.objects.create(title=title, client_role=client_role)
            document = ContractDocument.objects.create(
                contract=contract,
                original_filename=uploaded.name,
                file_extension=suffix,
                mime_type=uploaded.content_type or "",
                file_size_bytes=uploaded.size,
                file=uploaded,
                file_hash_sha256=_hash_uploaded_file(uploaded),
            )
            logger.info("Upload received: contract=%s document=%s (%s bytes)", contract.id, document.id, uploaded.size)

            summary_run = Summary.objects.create(contract=contract, document=document, run_id=io_utils.new_run_id())
            async_task("webreview.tasks.run_summary_task", summary_run.id, timeout=600, ack_failure=True)
            return redirect("webreview:summary_progress", summary_id=summary_run.id)
        logger.warning("Upload form invalid: %s", form.errors.as_text())
    else:
        form = ContractUploadForm()
    return render(request, "webreview/upload.html", {"form": form})


def summary_progress_view(request, summary_id: int):
    summary_run = get_object_or_404(Summary, id=summary_id)
    if summary_run.execution_status == Summary.SUCCEEDED:
        return redirect("webreview:summary_report", summary_id=summary_run.id)
    return render(
        request,
        "webreview/progress.html",
        {
            "heading": f"Summarising {summary_run.contract.title}",
            "subtitle": "This reads the document and produces a plain-English summary -- usually well under a minute.",
            "progress_percent": summary_run.progress_percent,
            "current_stage_label": summary_run.current_stage_label,
            "status_url": reverse("webreview:summary_status", args=[summary_run.id]),
            "report_url": reverse("webreview:summary_report", args=[summary_run.id]),
        },
    )


def summary_status_view(request, summary_id: int):
    summary_run = get_object_or_404(Summary, id=summary_id)
    stalled, stall_reason = stall.check_stall(
        summary_run.execution_status,
        summary_run.created_at,
        summary_run.updated_at,
        stall.RUNNING_STALL_SECONDS_SUMMARY,
    )
    return JsonResponse(
        {
            "execution_status": summary_run.execution_status,
            "current_stage_label": summary_run.current_stage_label,
            "progress_percent": summary_run.progress_percent,
            "incomplete_reason": summary_run.incomplete_reason,
            "stalled": stalled,
            "stall_reason": stall_reason,
        }
    )


def summary_report_view(request, summary_id: int):
    summary_run = get_object_or_404(Summary, id=summary_id)
    if summary_run.execution_status != Summary.SUCCEEDED:
        return redirect("webreview:summary_progress", summary_id=summary_run.id)
    return render(request, "webreview/summary_report.html", {"summary_run": summary_run})


def summary_download_pdf_view(request, summary_id: int):
    summary_run = get_object_or_404(Summary, id=summary_id)
    if not summary_run.summary_pdf:
        raise Http404("PDF not available for this summary.")
    safe_title = (
        "".join(c if c.isalnum() or c in "-_ " else "-" for c in summary_run.contract.title).strip() or "summary"
    )
    return FileResponse(
        summary_run.summary_pdf.open("rb"), as_attachment=True, filename=f"{safe_title}-summary.pdf"
    )
