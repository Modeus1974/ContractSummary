"""Stall detection for the progress pages -- computed live from timestamps, never stored,
so a fix (e.g. starting qcluster) is reflected on the very next poll with no stale flag left
over. Two distinct cases, since neither looks like a hard failure:

- Stuck "pending": the row was never even picked up by a worker. By far the most common
  real cause in this project so far -- qcluster simply wasn't running (see CLAUDE.md).
- Stuck "running": a worker claimed it but produced no progress update for far longer than
  that stage should ever take -- a hung/crashed worker process, not caught by the task's own
  try/except (which only catches exceptions raised *within* the worker process itself).
"""
from __future__ import annotations

from django.utils import timezone

PENDING_STALL_SECONDS = 30
RUNNING_STALL_SECONDS_SUMMARY = 120  # summarising is a single call, normally under a minute


def check_stall(execution_status: str, created_at, updated_at, running_threshold_seconds: int) -> tuple[bool, str]:
    """Returns (stalled, reason). `updated_at` is the timestamp of the most recent progress
    save -- for a still-"pending" row this equals created_at, so both branches use the same
    "how long since the relevant clock started" comparison, just against different clocks
    and different thresholds."""
    now = timezone.now()

    if execution_status == "pending":
        age = (now - created_at).total_seconds()
        if age > PENDING_STALL_SECONDS:
            return True, (
                f"Still queued after {int(age)}s with no worker picking it up. "
                "Is the background worker (qcluster) running?"
            )
        return False, ""

    if execution_status == "running":
        age = (now - updated_at).total_seconds()
        if age > running_threshold_seconds:
            return True, (
                f"No progress update in {int(age)}s, longer than this stage should normally "
                "take. The background worker may have crashed or hung."
            )
        return False, ""

    return False, ""
