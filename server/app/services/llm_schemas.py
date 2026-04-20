"""JSON Schemas for the three Milestone 3 LLM evaluation passes.

These schemas describe the *exact* JSON shapes that each AI pass must
produce.  They are pure data (Python ``dict`` objects in the JSON Schema
Draft 2020-12 dialect) so they can be consumed by ``jsonschema`` (or any
other validator) without importing FastAPI / SQLAlchemy.

Design-doc references:
    - §4 "AI Integration Specification"
        * Pass 1 — test reconciliation: classify failures as logic,
          environment, dependency, timeout, or memory.
        * Pass 2 — style and maintainability review: file-anchored
          findings sourced from RAG-retrieved style-guide excerpts and
          static-analysis output.
        * Pass 3 — synthesis into the final grading object with
          ``criteria_scores``, ``deterministic_score``, ``metadata``,
          and ``flags``.
    - §4 "All ``criteria_scores`` use a 0-100 point scale ... Each
      criterion includes a score level, evidence-based justification,
      confidence field, and optional ``RecommendationObject``.
      Recommendation objects include file path, line range, original
      snippet, revised snippet, and a Git-style diff."
    - Milestone 3 Dom task: "Define JSON schemas for each LLM pass output."
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

JSON_SCHEMA_DIALECT: Final[str] = "https://json-schema.org/draft/2020-12/schema"

# Per design-doc §4: failures are classified as one of these five buckets.
FAILURE_CLASSIFICATIONS: Final[tuple[str, ...]] = (
    "logic_bug",
    "environment",
    "dependency",
    "timeout",
    "memory",
)

# Severity values for Pass 2 style findings.  Mirrors the standard
# pylint/eslint severities.
STYLE_SEVERITIES: Final[tuple[str, ...]] = (
    "info",
    "warning",
    "error",
)

# Score levels for Pass 3 ``criteria_scores`` entries.  These mirror the
# rubric vocabulary used elsewhere in the system.
SCORE_LEVELS: Final[tuple[str, ...]] = (
    "Exemplary",
    "Proficient",
    "Developing",
    "Beginning",
    "NEEDS_HUMAN_REVIEW",
)

# Recognized values for the ``flags`` array on the final envelope.
KNOWN_FLAGS: Final[tuple[str, ...]] = (
    "NEEDS_HUMAN_REVIEW",
    "LOW_CONFIDENCE",
    "EVALUATION_FAILED",
    "no_match",
    "unsupported_language",
    "schema_repair_used",
)


# ---------------------------------------------------------------------------
# Reusable subschemas
# ---------------------------------------------------------------------------

# A 1-based, inclusive line range.  ``end`` must be >= ``start``.
LINE_RANGE_SCHEMA: Final[dict] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["start", "end"],
    "properties": {
        "start": {"type": "integer", "minimum": 1},
        "end": {"type": "integer", "minimum": 1},
    },
}

# Per design-doc §4: "Recommendation objects include file path, line
# range, original snippet, revised snippet, and a Git-style diff."
RECOMMENDATION_OBJECT_SCHEMA: Final[dict] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "file_path",
        "line_range",
        "original_snippet",
        "revised_snippet",
        "diff",
    ],
    "properties": {
        "file_path": {"type": "string", "minLength": 1},
        "line_range": LINE_RANGE_SCHEMA,
        "original_snippet": {"type": "string"},
        "revised_snippet": {"type": "string"},
        # A Git-style unified diff (``@@ -a,b +c,d @@`` headers, ``-``
        # / ``+`` line prefixes).  We only require non-empty content
        # here; deeper structural validation belongs to a parser.
        "diff": {"type": "string", "minLength": 1},
        "rationale": {"type": "string"},
    },
}


# ---------------------------------------------------------------------------
# Pass 1 — Test Reconciliation
# ---------------------------------------------------------------------------

PASS1_FAILURE_CLASSIFICATION_SCHEMA: Final[dict] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["test_name", "classification"],
    "properties": {
        "test_name": {"type": "string", "minLength": 1},
        "classification": {
            "type": "string",
            "enum": list(FAILURE_CLASSIFICATIONS),
        },
        "rubric_criterion": {"type": "string"},
        "evidence": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
    },
}

PASS1_OUTPUT_SCHEMA: Final[dict] = {
    "$schema": JSON_SCHEMA_DIALECT,
    "$id": "https://maple-a1/schemas/llm/pass1.json",
    "title": "MAPLE A1 Pass 1 — Test Reconciliation Output",
    "type": "object",
    "additionalProperties": False,
    "required": ["pass", "failures", "summary"],
    "properties": {
        "pass": {"const": "pass1"},
        "failures": {
            "type": "array",
            "items": PASS1_FAILURE_CLASSIFICATION_SCHEMA,
        },
        "summary": {"type": "string"},
        "needs_human_review": {"type": "boolean"},
        "notes": {"type": "string"},
    },
}


# ---------------------------------------------------------------------------
# Pass 2 — Style and Maintainability Review
# ---------------------------------------------------------------------------

PASS2_STYLE_FINDING_SCHEMA: Final[dict] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["file_path", "line_range", "rule_reference", "severity", "message"],
    "properties": {
        "file_path": {"type": "string", "minLength": 1},
        "line_range": LINE_RANGE_SCHEMA,
        # E.g. "PEP8:E501", "eslint:no-unused-vars".  Free-form so we
        # do not have to enumerate every linter rule.
        "rule_reference": {"type": "string", "minLength": 1},
        "severity": {"type": "string", "enum": list(STYLE_SEVERITIES)},
        "message": {"type": "string", "minLength": 1},
        # Optional snippet from the retrieved style-guide chunk that
        # justifies the finding.
        "style_guide_excerpt": {"type": "string"},
        # Optional structured metadata about which retrieved chunk was
        # cited (mirrors RAG return shape).
        "style_guide_source": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "source_title": {"type": "string"},
                "style_guide_version": {"type": "string"},
                "rule_id": {"type": "string"},
            },
        },
        "recommendation": RECOMMENDATION_OBJECT_SCHEMA,
    },
}

PASS2_OUTPUT_SCHEMA: Final[dict] = {
    "$schema": JSON_SCHEMA_DIALECT,
    "$id": "https://maple-a1/schemas/llm/pass2.json",
    "title": "MAPLE A1 Pass 2 — Style & Maintainability Review Output",
    "type": "object",
    "additionalProperties": False,
    "required": ["pass", "findings"],
    "properties": {
        "pass": {"const": "pass2"},
        # ``skipped`` is true when Pass 2 was orchestrated but no
        # eligible inputs were available (no linter violations, rubric
        # did not require style review, etc.).  In that case
        # ``findings`` MUST be empty.
        "skipped": {"type": "boolean"},
        "findings": {
            "type": "array",
            "items": PASS2_STYLE_FINDING_SCHEMA,
        },
        "retrieval_status": {
            "type": "string",
            "enum": ["ok", "no_match", "partial"],
        },
        "notes": {"type": "string"},
    },
}


# ---------------------------------------------------------------------------
# Pass 3 — Synthesis (MAPLE Standard Response Envelope)
# ---------------------------------------------------------------------------

CRITERIA_SCORE_SCHEMA: Final[dict] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "score", "level", "justification", "confidence"],
    "properties": {
        "name": {"type": "string", "minLength": 1},
        # 0-100 point scale per design-doc §4.
        "score": {"type": "number", "minimum": 0, "maximum": 100},
        "level": {"type": "string", "enum": list(SCORE_LEVELS)},
        "justification": {"type": "string", "minLength": 1},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        # Recommendations are optional per criterion and only emitted
        # when an exact file path, line range, and snippet are present
        # in evidence (design-doc §4).
        "recommendations": {
            "type": "array",
            "items": RECOMMENDATION_OBJECT_SCHEMA,
        },
        "flags": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
}

PASS3_METADATA_SCHEMA: Final[dict] = {
    "type": "object",
    # Allow the pipeline to merge in M2 metadata (language, exit_code,
    # resource_constraint_metadata, test_summary) plus M3 fields like
    # ``style_guide_version``.  We keep this loose so M2 and M3 metadata
    # can coexist without schema drift.
    "additionalProperties": True,
    "properties": {
        "style_guide_version": {"type": ["string", "array", "null"]},
        "language": {"type": ["object", "null"]},
        "exit_code": {"type": ["integer", "null"]},
    },
}

PASS3_OUTPUT_SCHEMA: Final[dict] = {
    "$schema": JSON_SCHEMA_DIALECT,
    "$id": "https://maple-a1/schemas/llm/pass3.json",
    "title": "MAPLE A1 Pass 3 — MAPLE Standard Response Envelope",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "criteria_scores",
        "deterministic_score",
        "metadata",
        "flags",
    ],
    "properties": {
        "criteria_scores": {
            "type": "array",
            "minItems": 0,
            "items": CRITERIA_SCORE_SCHEMA,
        },
        "deterministic_score": {
            "type": ["number", "null"],
            "minimum": 0,
            "maximum": 100,
        },
        "metadata": PASS3_METADATA_SCHEMA,
        "flags": {
            "type": "array",
            "items": {"type": "string"},
        },
        # Optional convenience field — Pass 3 may emit a top-level
        # narrative summary alongside the per-criterion justifications.
        "summary": {"type": "string"},
    },
}


# ---------------------------------------------------------------------------
# Public registry — handy for the validator/repair module to look up by name
# ---------------------------------------------------------------------------

SCHEMA_REGISTRY: Final[dict[str, dict]] = {
    "pass1": PASS1_OUTPUT_SCHEMA,
    "pass2": PASS2_OUTPUT_SCHEMA,
    "pass3": PASS3_OUTPUT_SCHEMA,
    "recommendation_object": RECOMMENDATION_OBJECT_SCHEMA,
}


def get_schema(name: str) -> dict:
    """Return the JSON Schema dict for *name* or raise ``KeyError``.

    Convenience accessor used by the validator/repair module so callers
    do not have to import individual constants.
    """
    return SCHEMA_REGISTRY[name]


__all__ = [
    "FAILURE_CLASSIFICATIONS",
    "JSON_SCHEMA_DIALECT",
    "KNOWN_FLAGS",
    "LINE_RANGE_SCHEMA",
    "PASS1_FAILURE_CLASSIFICATION_SCHEMA",
    "PASS1_OUTPUT_SCHEMA",
    "PASS2_OUTPUT_SCHEMA",
    "PASS2_STYLE_FINDING_SCHEMA",
    "PASS3_OUTPUT_SCHEMA",
    "RECOMMENDATION_OBJECT_SCHEMA",
    "SCHEMA_REGISTRY",
    "SCORE_LEVELS",
    "STYLE_SEVERITIES",
    "get_schema",
]
