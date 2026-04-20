"""Deterministic scoring: map test pass/fail counts to a 0-100 score.

Pure function — no database, no network, no FastAPI dependencies.
"""

from __future__ import annotations


def calculate_deterministic_score(
    test_results: dict,
    rubric_content: dict | list | str | None = None,
) -> float:
    """Return a score between 0.0 and 100.0.

    Scoring strategy:
      1. If *rubric_content* is a dict with weighted ``criteria`` whose names
         can be mapped to individual test names, distribute points
         proportionally across criteria.
      2. Otherwise fall back to ``(passed / effective_total) * 100``.

    Skipped tests are excluded from the denominator.  Zero effective tests
    returns 0.0 (no division by zero).
    """
    passed = test_results.get("passed", 0)
    failed = test_results.get("failed", 0)
    errors = test_results.get("errors", 0)
    skipped = test_results.get("skipped", 0)

    effective_total = passed + failed + errors
    if effective_total == 0:
        return 0.0

    criteria = _extract_weighted_criteria(rubric_content)
    if criteria is not None:
        return _weighted_score(test_results, criteria, effective_total)

    return round((passed / effective_total) * 100, 2)


def _extract_weighted_criteria(
    rubric_content: dict | list | str | None,
) -> list[dict] | None:
    """Return the criteria list when it contains at least one ``weight``."""
    if not isinstance(rubric_content, dict):
        return None
    criteria = rubric_content.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return None
    if not any(isinstance(c, dict) and "weight" in c for c in criteria):
        return None
    return criteria


def _weighted_score(
    test_results: dict,
    criteria: list[dict],
    effective_total: int,
) -> float:
    """Map individual tests to rubric criteria by name and sum weighted points.

    For each criterion that carries a ``weight`` and a ``name``, find any
    matching tests (case-insensitive substring).  If a criterion has at least
    one mapped test, its contribution is ``weight * (mapped_passed / mapped_total)``.
    Criteria with no matching tests fall back to the global pass ratio.
    """
    tests: list[dict] = test_results.get("tests", [])
    global_ratio = test_results.get("passed", 0) / effective_total if effective_total else 0.0

    total_weight = 0.0
    earned = 0.0

    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        weight = criterion.get("weight")
        if weight is None:
            continue
        weight = float(weight)
        total_weight += weight
        name = (criterion.get("name") or "").lower()

        mapped = [
            t for t in tests
            if isinstance(t, dict) and name and name in (t.get("name") or "").lower()
        ]
        if mapped:
            mp = sum(1 for t in mapped if t.get("status") == "passed")
            earned += weight * (mp / len(mapped))
        else:
            earned += weight * global_ratio

    if total_weight == 0:
        return round(global_ratio * 100, 2)

    return round((earned / total_weight) * 100, 2)
