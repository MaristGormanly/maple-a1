"""Debug instrumentation helper (debug session d6fd1e).

Writes a single NDJSON line per call to the workspace-local log file.
Removed once the live AI-phase issue is verified fixed.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

_LOG_PATH = Path("/Users/jaydenxm419/maple-a1/.cursor/debug-d6fd1e.log")


def dlog(
    *,
    location: str,
    message: str,
    data: dict[str, Any] | None = None,
    hypothesis_id: str = "",
    run_id: str = "run1",
) -> None:
    try:
        payload = {
            "sessionId": "d6fd1e",
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data or {},
            "timestamp": int(time.time() * 1000),
        }
        _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")
    except Exception:
        pass
