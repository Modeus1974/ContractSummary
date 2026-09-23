from django.urls import path

from webreview import views

app_name = "webreview"

urlpatterns = [
    path("", views.upload_view, name="upload"),
    path("summaries/<int:summary_id>/", views.summary_progress_view, name="summary_progress"),
    path("summaries/<int:summary_id>/status/", views.summary_status_view, name="summary_status"),
    path("summaries/<int:summary_id>/report/", views.summary_report_view, name="summary_report"),
    path(
        "summaries/<int:summary_id>/download/pdf/",
        views.summary_download_pdf_view,
        name="summary_download_pdf",
    ),
]
