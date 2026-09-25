from django.urls import path
from django.views.generic import RedirectView

from webreview import views

app_name = "webreview"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="webreview:summarise", permanent=False), name="home"),
    path("summarise/", views.upload_view, name="summarise"),
    path("full-stack/", views.full_stack_view, name="full_stack"),
    path("nlp/", views.nlp_view, name="nlp"),
    path("summaries/<int:summary_id>/", views.summary_progress_view, name="summary_progress"),
    path("summaries/<int:summary_id>/status/", views.summary_status_view, name="summary_status"),
    path("summaries/<int:summary_id>/report/", views.summary_report_view, name="summary_report"),
    path(
        "summaries/<int:summary_id>/download/pdf/",
        views.summary_download_pdf_view,
        name="summary_download_pdf",
    ),
]
