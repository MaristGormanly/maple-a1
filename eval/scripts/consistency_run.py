"""Consistency-run variance helper (M4 task 4.C.4).

Given N >= 2 independent evaluation runs of the same submission,
compute the per-criterion score range (max - min) and whether it
meets the design-doc §5 target (<=3/100).

The CLI layer that actually *drives* the 5 repeated runs against
/evaluate is intentionally omitted here — it requires a live backend
and a bypass-cache mechanism (e.g., appending a per-run nonce to
the rubric before fingerprinting). That glue belongs in a live
operator script, not in a unit-tested pure helper.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


TARGET_RANGE = 3


def compute_per_criterion_variance(
    runs: list[list[dict[str, Any]]],
    *,
    target: int = TARGET_RANGE,
) -> dict[str, dict[str, Any]]:
    if len(runs) < 2:
        raise ValueError("consistency check requires at least 2 runs")

    scores_by_criterion: dict[str, list[int]] = {}
    for run in runs:
        for c in run:
            scores_by_criterion.setdefault(c["criterion_id"], []).append(c["score"])

    out: dict[str, dict[str, Any]] = {}
    for cid, scores in scores_by_criterion.items():
        rng = max(scores) - min(scores)
        out[cid] = {
            "scores": scores,
            "range": rng,
            "within_target": rng <= target,
        }
    return out


def _write_csv(variance: dict[str, dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["criterion_id", "scores", "range", "within_target"]
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for cid, info in variance.items():
            writer.writerow(
                {
                    "criterion_id": cid,
                    "scores": ";".join(str(s) for s in info["scores"]),
                    "range": info["range"],
                    "within_target": info["within_target"],
                }
            )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Compute per-criterion consistency variance across repeated runs."
    )
    p.add_argument(
        "--runs",
        required=True,
        type=Path,
        help="JSON file: list of runs, each a list of {criterion_id, score}",
    )
    p.add_argument("--out", required=True, type=Path, help="Output CSV path")
    args = p.parse_args(argv)

    runs = json.loads(args.runs.read_text())
    variance = compute_per_criterion_variance(runs)
    _write_csv(variance, args.out)
    worst = max(info["range"] for info in variance.values())
    print(f"worst_range={worst} target<={TARGET_RANGE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
