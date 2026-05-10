"""Append a row to eval/results/pilot-run-log.csv (M4 task 4.C.2).

One row per pilot submission. Columns are fixed; missing columns
raise ValueError at the Python layer so the operator catches schema
drift before the row is written.

CLI:
    python -m eval.scripts.pilot_run_log \
        --csv eval/results/pilot-run-log.csv \
        --submission-id sub_1 \
        --commit-hash abc123 \
        --latency-ms 12345 \
        --models-used gemini-3.1-pro-preview \
        --cost-usd 0.42
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Mapping


REQUIRED_COLUMNS: tuple[str, ...] = (
    "submission_id",
    "commit_hash",
    "latency_ms_total",
    "models_used",
    "estimated_cost_usd",
)


def append_run_row(csv_path: Path, row: Mapping[str, Any]) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in row]
    if missing:
        raise ValueError(f"pilot-run-log row missing columns: {missing}")
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: row[k] for k in REQUIRED_COLUMNS})


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Append one row to the pilot run log.")
    p.add_argument("--csv", required=True, type=Path)
    p.add_argument("--submission-id", required=True)
    p.add_argument("--commit-hash", required=True)
    p.add_argument("--latency-ms", type=int, required=True)
    p.add_argument("--models-used", required=True)
    p.add_argument("--cost-usd", type=float, required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    append_run_row(
        args.csv,
        {
            "submission_id": args.submission_id,
            "commit_hash": args.commit_hash,
            "latency_ms_total": args.latency_ms,
            "models_used": args.models_used,
            "estimated_cost_usd": args.cost_usd,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
