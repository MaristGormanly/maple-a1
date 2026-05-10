"""Grading-time CSV helper (M4 task 4.C.6).

Schema-validates and appends one row per grading event. Each
submission has two rows: one for manual grading (baseline) and one
for AI-review time. Target per design-doc §5: manual ~15 min,
ai_review < 3 min.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Mapping


ALLOWED_MODES = {"manual", "ai_review"}
FIELDS: tuple[str, ...] = ("submission_id", "mode", "seconds")


def validate_row(row: Mapping[str, Any]) -> dict[str, Any]:
    missing = [f for f in FIELDS if f not in row]
    if missing:
        raise ValueError(f"grading-time row missing columns: {missing}")
    if not isinstance(row["submission_id"], str) or not row["submission_id"]:
        raise ValueError("submission_id must be a non-empty string")
    if row["mode"] not in ALLOWED_MODES:
        raise ValueError(f"mode must be one of {ALLOWED_MODES}; got {row['mode']!r}")
    seconds = row["seconds"]
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        raise ValueError("seconds must be numeric")
    if seconds < 0:
        raise ValueError("seconds must be >= 0")
    return dict(row)


def append_row(csv_path: Path, row: Mapping[str, Any]) -> None:
    validated = validate_row(row)
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: validated[k] for k in FIELDS})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Append a grading-time row.")
    p.add_argument("--csv", required=True, type=Path)
    p.add_argument("--submission-id", required=True)
    p.add_argument("--mode", required=True, choices=sorted(ALLOWED_MODES))
    p.add_argument("--seconds", required=True, type=float)
    args = p.parse_args(argv)

    append_row(
        args.csv,
        {
            "submission_id": args.submission_id,
            "mode": args.mode,
            "seconds": args.seconds,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
