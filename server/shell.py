"""Subprocess wrapper. All tools go through `run_cmd` — no bare subprocess.run.

Enforces timeout, captures stdout/stderr as text, returns a structured dict.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path


def run_cmd(
    cmd: list[str],
    cwd: Path,
    timeout: int = 60,
    stdin: str | None = None,
) -> dict:
    started = time.monotonic()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        return {
            "command": cmd,
            "returncode": None,
            "stdout": (e.stdout or "") if isinstance(e.stdout, str) else "",
            "stderr": (e.stderr or "") if isinstance(e.stderr, str) else "",
            "duration_s": round(time.monotonic() - started, 3),
            "timed_out": True,
        }
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "duration_s": round(time.monotonic() - started, 3),
        "timed_out": False,
    }
