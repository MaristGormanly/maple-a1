"""Calibration ratings CSV helper (M4 task 4.C.5).

Validates instructor feedback-usefulness ratings on a 1-5 integer
scale across three axes (clarity, relevance, instructional_value).
Target per design-doc §5: average >= 4.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Mapping


RATING_FIELDS: tuple[str, ...] = ("clarity", "relevance", "instructional_value")
FIELDS: tuple[str, ...] = ("submission_id",) + RATING_FIELDS


def validate_ratings(row: Mapping[str, Any]) -> dict[str, Any]:
    missing = [f for f in FIELDS if f not in row]
    if missing:
        raise ValueError(f"calibration-ratings row missing columns: {missing}")
    if not isinstance(row["submission_id"], str) or not row["submission_id"]:
        raise ValueError("submission_id must be a non-empty string")
    for field in RATING_FIELDS:
        value = row[field]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field} must be an integer rating (1-5); got {value!r}")
        if not 1 <= value <= 5:
            raise ValueError(f"{field} must be between 1 and 5; got {value}")
    return dict(row)


def append_row(csv_path: Path, row: Mapping[str, Any]) -> None:
    validated = validate_ratings(row)
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists()
    with csv_path.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow({k: validated[k] for k in FIELDS})


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Append a calibration-ratings row.")
    p.add_argument("--csv", required=True, type=Path)
    p.add_argument("--submission-id", required=True)
    p.add_argument("--clarity", type=int, required=True)
    p.add_argument("--relevance", type=int, required=True)
    p.add_argument("--instructional-value", type=int, required=True)
    args = p.parse_args(argv)

    append_row(
        args.csv,
        {
            "submission_id": args.submission_id,
            "clarity": args.clarity,
            "relevance": args.relevance,
            "instructional_value": args.instructional_value,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
