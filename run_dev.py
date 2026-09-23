#!/usr/bin/env python
"""Starts the Django dev server and the django-q2 worker together, so there's one command
to run instead of two -- see CLAUDE.md's process-hygiene notes for why this exists: a
`qcluster` that's never started is the single most common cause of a "stalled" progress page
in this project so far. Ctrl+C stops both cleanly.

This does not replace running them separately when you specifically want to watch one
process's log output on its own (e.g. deep-debugging a hung worker) -- it's the default
for ordinary testing, not the only way to start things.
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable
HOST = "127.0.0.1"


def _port_in_use(host: str, port: int) -> bool:
    """A connect()-based check only detects an active listener -- it misses a port stuck
    in TIME_WAIT after a process died, which still fails to *bind*. Test with a real bind,
    the same operation runserver itself performs, so this can't produce a false negative."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return True
    return False


def _kill_process_tree(pid: int) -> None:
    """Popen.terminate() on Windows only signals the direct child -- it does not cascade to
    grandchildren (e.g. django-q2's forked sentinel/worker), which are then orphaned rather
    than stopped. taskkill /T kills the whole tree."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        import signal

        try:
            import os

            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except ProcessLookupError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    port = args.port

    if _port_in_use(HOST, port):
        print(
            f"Port {port} is already in use -- a runserver from an earlier session is likely "
            "still running (see CLAUDE.md: these processes outlive a session). Stop it first "
            f"(PowerShell: Get-NetTCPConnection -LocalPort {port}, then Stop-Process -Id <pid>)."
        )
        return 1

    print(f"Starting runserver ({HOST}:{port}) and qcluster together. Press Ctrl+C to stop both.\n")

    processes = [
        subprocess.Popen([PYTHON, "manage.py", "runserver", f"{HOST}:{port}", "--noreload"], cwd=PROJECT_ROOT),
        subprocess.Popen([PYTHON, "manage.py", "qcluster"], cwd=PROJECT_ROOT),
    ]

    try:
        while True:
            for p in processes:
                if p.poll() is not None:
                    print(f"\nProcess PID {p.pid} exited (code {p.returncode}) -- stopping the other one too.")
                    raise KeyboardInterrupt
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        for p in processes:
            if p.poll() is None:
                _kill_process_tree(p.pid)
        for p in processes:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass  # taskkill /F already forced it; a lingering wait() here isn't fatal
    return 0


if __name__ == "__main__":
    sys.exit(main())
