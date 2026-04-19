"""Unit tests for ``app.services.llm_schemas``.

These tests pin the contract for each LLM-pass JSON Schema by feeding
both a valid and an intentionally invalid instance through
``jsonschema`` and asserting accept/reject behavior.
"""

from __future__ import annotations

import copy
import unittest

from jsonschema import Draft202012Validator, ValidationError

from app.services.llm_schemas import (
    PASS1_OUTPUT_SCHEMA,
    PASS2_OUTPUT_SCHEMA,
    PASS3_OUTPUT_SCHEMA,
    RECOMMENDATION_OBJECT_SCHEMA,
    SCHEMA_REGISTRY,
    get_schema,
)


def _validator(schema: dict) -> Draft202012Validator:
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


# ---------------------------------------------------------------------------
# Reusable example payloads
# ---------------------------------------------------------------------------

_VALID_RECOMMENDATION: dict = {
    "file_path": "src/utils/math.py",
    "line_range": {"start": 10, "end": 14},
    "original_snippet": "def add(a, b):\n    return a - b\n",
    "revised_snippet": "def add(a, b):\n    return a + b\n",
    "diff": (
        "@@ -10,3 +10,3 @@\n"
        " def add(a, b):\n"
        "-    return a - b\n"
        "+    return a + b\n"
    ),
    "rationale": "The implementation subtracted instead of added.",
}


_VALID_PASS1: dict = {
    "pass": "pass1",
    "failures": [
        {
            "test_name": "tests/test_math.py::test_add",
            "classification": "logic_bug",
            "rubric_criterion": "Arithmetic correctness",
            "evidence": "AssertionError: expected 5, got -1",
            "confidence": 0.92,
        },
        {
            "test_name": "tests/test_io.py::test_reads_file",
            "classification": "environment",
            "evidence": "FileNotFoundError: data.csv",
            "confidence": 0.40,
        },
    ],
    "summary": "Logic bug in add(); environment issue prevents file IO test.",
    "needs_human_review": False,
}


_VALID_PASS2: dict = {
    "pass": "pass2",
    "skipped": False,
    "findings": [
        {
            "file_path": "src/utils/math.py",
            "line_range": {"start": 10, "end": 10},
            "rule_reference": "PEP8:E501",
            "severity": "warning",
            "message": "Line too long (120 > 100 characters).",
            "style_guide_excerpt": "Limit lines to 100 characters.",
            "style_guide_source": {
                "source_title": "PEP 8",
                "style_guide_version": "2024-09-01",
                "rule_id": "E501",
            },
            "recommendation": _VALID_RECOMMENDATION,
        }
    ],
    "retrieval_status": "ok",
}


_VALID_PASS3: dict = {
    "criteria_scores": [
        {
            "name": "Correctness",
            "score": 87.5,
            "level": "Proficient",
            "justification": "12/14 unit tests pass; remaining failures are edge cases.",
            "confidence": 0.88,
            "recommendations": [_VALID_RECOMMENDATION],
            "flags": [],
        },
        {
            "name": "Style",
            "score": 70,
            "level": "Developing",
            "justification": "Several PEP8 line-length violations remain.",
            "confidence": 0.75,
        },
    ],
    "deterministic_score": 85.7,
    "metadata": {
        "language": {"name": "python", "version": "3.11"},
        "exit_code": 0,
        "style_guide_version": "2024-09-01",
    },
    "flags": ["LOW_CONFIDENCE"],
    "summary": "Submission is functionally strong but stylistically inconsistent.",
}


# ---------------------------------------------------------------------------
# Pass 1
# ---------------------------------------------------------------------------


class Pass1SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = _validator(PASS1_OUTPUT_SCHEMA)

    def test_valid_instance_passes(self) -> None:
        self.validator.validate(_VALID_PASS1)

    def test_unknown_classification_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_PASS1)
        bad["failures"][0]["classification"] = "cosmic_rays"
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_missing_summary_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_PASS1)
        bad.pop("summary")
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_pass_const_is_enforced(self) -> None:
        bad = copy.deepcopy(_VALID_PASS1)
        bad["pass"] = "pass2"
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)


# ---------------------------------------------------------------------------
# Pass 2
# ---------------------------------------------------------------------------


class Pass2SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = _validator(PASS2_OUTPUT_SCHEMA)

    def test_valid_instance_passes(self) -> None:
        self.validator.validate(_VALID_PASS2)

    def test_empty_findings_allowed_when_skipped(self) -> None:
        instance = {"pass": "pass2", "skipped": True, "findings": []}
        self.validator.validate(instance)

    def test_invalid_severity_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_PASS2)
        bad["findings"][0]["severity"] = "catastrophic"
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_missing_rule_reference_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_PASS2)
        bad["findings"][0].pop("rule_reference")
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_finding_recommendation_must_have_diff(self) -> None:
        bad = copy.deepcopy(_VALID_PASS2)
        bad["findings"][0]["recommendation"].pop("diff")
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)


# ---------------------------------------------------------------------------
# Pass 3 — MAPLE Standard Response Envelope
# ---------------------------------------------------------------------------


class Pass3SchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = _validator(PASS3_OUTPUT_SCHEMA)

    def test_valid_envelope_passes(self) -> None:
        self.validator.validate(_VALID_PASS3)

    def test_score_above_100_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_PASS3)
        bad["criteria_scores"][0]["score"] = 110
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_unknown_level_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_PASS3)
        bad["criteria_scores"][0]["level"] = "Stellar"
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_confidence_out_of_range_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_PASS3)
        bad["criteria_scores"][0]["confidence"] = 1.5
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_missing_required_envelope_field_rejected(self) -> None:
        for field in ("criteria_scores", "deterministic_score", "metadata", "flags"):
            with self.subTest(missing=field):
                bad = copy.deepcopy(_VALID_PASS3)
                bad.pop(field)
                with self.assertRaises(ValidationError):
                    self.validator.validate(bad)

    def test_deterministic_score_may_be_null(self) -> None:
        instance = copy.deepcopy(_VALID_PASS3)
        instance["deterministic_score"] = None
        self.validator.validate(instance)


# ---------------------------------------------------------------------------
# RecommendationObject — required by both Pass 2 and Pass 3
# ---------------------------------------------------------------------------


class RecommendationObjectSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = _validator(RECOMMENDATION_OBJECT_SCHEMA)

    def test_valid_recommendation_passes(self) -> None:
        self.validator.validate(_VALID_RECOMMENDATION)

    def test_required_fields_enforced(self) -> None:
        for field in (
            "file_path",
            "line_range",
            "original_snippet",
            "revised_snippet",
            "diff",
        ):
            with self.subTest(missing=field):
                bad = copy.deepcopy(_VALID_RECOMMENDATION)
                bad.pop(field)
                with self.assertRaises(ValidationError):
                    self.validator.validate(bad)

    def test_empty_diff_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_RECOMMENDATION)
        bad["diff"] = ""
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_line_range_requires_start_and_end(self) -> None:
        bad = copy.deepcopy(_VALID_RECOMMENDATION)
        bad["line_range"] = {"start": 1}
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)

    def test_extra_properties_rejected(self) -> None:
        bad = copy.deepcopy(_VALID_RECOMMENDATION)
        bad["unexpected"] = "value"
        with self.assertRaises(ValidationError):
            self.validator.validate(bad)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class RegistryTests(unittest.TestCase):
    def test_registry_exposes_all_passes(self) -> None:
        for key in ("pass1", "pass2", "pass3", "recommendation_object"):
            self.assertIn(key, SCHEMA_REGISTRY)
            self.assertIs(get_schema(key), SCHEMA_REGISTRY[key])

    def test_get_schema_unknown_raises(self) -> None:
        with self.assertRaises(KeyError):
            get_schema("pass99")


if __name__ == "__main__":
    unittest.main()
