"""Compute AI-vs-instructor rubric alignment (M4 task 4.C.3).

Takes two parallel lists of criterion scores (AI output and
instructor blind grading) and returns per-criterion deltas plus the
headline metric: pct_within_5_points. Success target per
design-doc §5 is >=0.80.

CLI writes a CSV. Python API is pure.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def compute_deltas(
    ai: list[dict[str, Any]],
    instructor: list[dict[str, Any]],
    *,
    threshold: int = 5,
) -> dict[str, Any]:
    if len(ai) != len(instructor):
        raise ValueError(
            f"criterion count mismatch: ai={len(ai)} instructor={len(instructor)}"
        )
    ai_by_id = {c["criterion_id"]: c["score"] for c in ai}
    instr_by_id = {c["criterion_id"]: c["score"] for c in instructor}
    if set(ai_by_id) != set(instr_by_id):
        raise ValueError(
            f"criterion id mismatch: ai={sorted(ai_by_id)} "
            f"instructor={sorted(instr_by_id)}"
        )

    rows: list[dict[str, Any]] = []
    for cid in ai_by_id:
        delta = abs(ai_by_id[cid] - instr_by_id[cid])
        rows.append(
            {
                "criterion_id": cid,
                "ai_score": ai_by_id[cid],
                "instructor_score": instr_by_id[cid],
                "delta": delta,
                "within_target": delta <= threshold,
            }
        )
    within = sum(1 for r in rows if r["within_target"])
    return {
        "rows": rows,
        "pct_within_5_points": within / len(rows) if rows else 0.0,
    }


def _write_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["criterion_id", "ai_score", "instructor_score", "delta", "within_target"]
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Compute AI-vs-instructor rubric deltas.")
    p.add_argument("--ai", required=True, type=Path, help="JSON file with AI criteria_scores")
    p.add_argument("--instructor", required=True, type=Path, help="JSON file with instructor scores")
    p.add_argument("--out", required=True, type=Path, help="Output CSV path")
    args = p.parse_args(argv)

    ai = json.loads(args.ai.read_text())
    instructor = json.loads(args.instructor.read_text())
    result = compute_deltas(ai, instructor)
    _write_csv(result["rows"], args.out)
    print(f"pct_within_5_points={result['pct_within_5_points']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
