"""Local-dev-only self-healing for the recurring "qcluster isn't running" incident (see
CLAUDE.md's process-hygiene notes -- this has happened repeatedly, always the same way: a
worker was never started, and nothing in the app itself noticed).

Detection is a heartbeat file, not django-q2's own Stat/cluster-monitoring API: that API
stores its heartbeat through Django's cache framework (contract_reviewer.runtime's global
was a *conceptually* similar trap -- see ARCHITECTURE.md #3), and this project runs the
default LocMemCache, which is private to each process. A `runserver` process could never
see a `qcluster` process's heartbeat through it without configuring a shared cache backend.
A plain file next to `.runs/` sidesteps that entirely.

Deliberately dev-only (gated on settings.DEBUG): in production, PythonAnywhere's Always-on
task already supervises and restarts `qcluster` on its own (see CLAUDE.md's "Production
deployment" section) -- a second auto-spawn from inside a WSGI worker would just create a
duplicate cluster, not fix anything.
"""
from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

from django.conf import settings

from contract_reviewer.io_utils import RUNS_DIR

logger = logging.getLogger("webreview")

HEARTBEAT_PATH = RUNS_DIR / "qcluster.heartbeat"
LOCK_PATH = RUNS_DIR / "qcluster_local.lock"
HEARTBEAT_INTERVAL_SECONDS = 10
# Generous multiple of the interval so one delayed tick (GC pause, system load) doesn't
# read as a dead worker.
STALE_AFTER_SECONDS = 25
# How long a spawn attempt gets before we're willing to try spawning again -- covers a
# spawn that silently failed, without retrying so fast it piles up duplicate processes.
LOCK_STALE_AFTER_SECONDS = 20


def _age_seconds(path: Path) -> float | None:
    try:
        return time.time() - path.stat().st_mtime
    except FileNotFoundError:
        return None


def is_worker_alive() -> bool:
    age = _age_seconds(HEARTBEAT_PATH)
    return age is not None and age < STALE_AFTER_SECONDS


def ensure_worker_running() -> None:
    """Called from upload_view. No-op in production (see module docstring). In dev, if the
    heartbeat looks dead and nothing has attempted a spawn recently, starts one `qcluster_local`
    as a detached process and returns immediately -- the newly queued task just waits in the
    pending state (same as any other task) until that process finishes importing and starts
    pulling from the queue."""
    if not settings.DEBUG:
        return
    if is_worker_alive():
        return

    lock_age = _age_seconds(LOCK_PATH)
    if lock_age is not None and lock_age < LOCK_STALE_AFTER_SECONDS:
        return  # another request already triggered a spawn very recently

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text("")  # touch, marks "a spawn attempt is in flight"

    logger.warning("qcluster heartbeat missing or stale -- auto-starting a local worker")
    log_path = RUNS_DIR / "qcluster_auto.log"
    with open(log_path, "a") as log_file:
        subprocess.Popen(
            [sys.executable, str(settings.BASE_DIR / "manage.py"), "qcluster_local"],
            cwd=str(settings.BASE_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
