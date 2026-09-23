from __future__ import annotations

from django import forms
from django.conf import settings

from contract_reviewer.document_extract import SUPPORTED_EXTENSIONS


class ContractUploadForm(forms.Form):
    title = forms.CharField(max_length=255, required=False, help_text="Optional -- defaults to the filename.")
    file = forms.FileField(help_text="PDF or Word (.docx) only.")
    client_role = forms.CharField(max_length=100, required=False, help_text="e.g. tenant, landlord, employer.")

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        suffix = "." + uploaded.name.rsplit(".", 1)[-1].lower() if "." in uploaded.name else ""
        if suffix not in SUPPORTED_EXTENSIONS:
            raise forms.ValidationError(f"Unsupported file type '{suffix}'. Allowed: {', '.join(SUPPORTED_EXTENSIONS)}.")
        if uploaded.size > settings.MAX_UPLOAD_SIZE_BYTES:
            max_mb = settings.MAX_UPLOAD_SIZE_BYTES // (1024 * 1024)
            raise forms.ValidationError(f"File too large (max {max_mb} MB).")
        return uploaded
