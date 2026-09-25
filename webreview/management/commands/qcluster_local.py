"""Local-dev wrapper around django-q2's own `qcluster` command: identical behaviour, plus a
periodic heartbeat file (webreview.worker_health) so upload_view can tell whether a worker
is actually alive and auto-start one if not. See worker_health.py's module docstring for why
this can't just use django-q2's own Stat/cluster-monitoring API.

Not used in production -- the PythonAnywhere Always-on task keeps running the plain
`manage.py qcluster` unchanged (see CLAUDE.md's "Production deployment" section); it doesn't
need a heartbeat, since PythonAnywhere already restarts it on crash.
"""
from __future__ import annotations

import threading
import time

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone
from django_q.cluster import Cluster

from webreview.worker_health import HEARTBEAT_INTERVAL_SECONDS, HEARTBEAT_PATH


def _write_heartbeat_loop() -> None:
    HEARTBEAT_PATH.parent.mkdir(parents=True, exist_ok=True)
    while True:
        HEARTBEAT_PATH.write_text(timezone.now().isoformat())
        time.sleep(HEARTBEAT_INTERVAL_SECONDS)


class Command(BaseCommand):
    help = "Starts a Django Q Cluster with a local-dev heartbeat file for auto-recovery."

    def handle(self, *args, **options):
        settings.SECRET_KEY  # same guard django-q2's own qcluster command performs
        threading.Thread(target=_write_heartbeat_loop, daemon=True).start()
        Cluster().start()
