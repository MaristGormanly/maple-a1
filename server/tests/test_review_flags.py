"""Unit tests for ``app.services.review_flags`` (DB-free)."""

from __future__ import annotations

import unittest

from app.services.review_flags import (
    DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE,
    NEEDS_HUMAN_REVIEW,
    NO_MATCH,
    UNSUPPORTED_LANGUAGE,
    compute_review_flags,
    determine_terminal_status,
)


def _envelope(criteria, *, flags=None) -> dict:
    return {
        "criteria_scores": criteria,
        "deterministic_score": 80.0,
        "metadata": {},
        "flags": list(flags or []),
    }


def _crit(*, name="C", score=80, level="Proficient", confidence=0.9) -> dict:
    return {
        "name": name,
        "score": score,
        "level": level,
        "justification": "ok",
        "confidence": confidence,
    }


class ComputeReviewFlagsHappyPathTests(unittest.TestCase):
    def test_clean_envelope_yields_completed(self) -> None:
        env = _envelope([_crit(confidence=0.9), _crit(name="D", confidence=0.85)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="python"
        )
        self.assertNotIn(NEEDS_HUMAN_REVIEW, flags)
        self.assertFalse(awaiting)
        self.assertEqual(determine_terminal_status(awaiting), "Completed")

    def test_existing_flags_are_preserved_without_duplication(self) -> None:
        env = _envelope([_crit(confidence=0.9)], flags=["custom_flag", LOW_CONFIDENCE])
        flags, _ = compute_review_flags(
            env, retrieval_status="ok", language="python"
        )
        self.assertIn("custom_flag", flags)
        self.assertEqual(flags.count(LOW_CONFIDENCE), 1)

    def test_envelope_is_not_mutated(self) -> None:
        env = _envelope([_crit(confidence=0.9)])
        original_flags = list(env["flags"])
        compute_review_flags(env, retrieval_status="ok", language="python")
        self.assertEqual(env["flags"], original_flags)


class AmbiguousRubricTriggerTests(unittest.TestCase):
    def test_per_criterion_needs_human_review_level_triggers(self) -> None:
        env = _envelope(
            [
                _crit(confidence=0.95),
                _crit(name="Style", level=NEEDS_HUMAN_REVIEW, confidence=0.95),
            ]
        )
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="python"
        )
        self.assertIn(NEEDS_HUMAN_REVIEW, flags)
        self.assertTrue(awaiting)
        self.assertEqual(determine_terminal_status(awaiting), "Awaiting Review")

    def test_envelope_flag_already_present_propagates(self) -> None:
        env = _envelope([_crit(confidence=0.9)], flags=[NEEDS_HUMAN_REVIEW])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="python"
        )
        self.assertEqual(flags.count(NEEDS_HUMAN_REVIEW), 1)
        self.assertTrue(awaiting)


class LowConfidenceTriggerTests(unittest.TestCase):
    def test_below_default_threshold_triggers(self) -> None:
        env = _envelope([_crit(confidence=0.55)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="python"
        )
        self.assertIn(LOW_CONFIDENCE, flags)
        self.assertIn(NEEDS_HUMAN_REVIEW, flags)
        self.assertTrue(awaiting)

    def test_at_threshold_does_not_trigger(self) -> None:
        env = _envelope([_crit(confidence=DEFAULT_LOW_CONFIDENCE_THRESHOLD)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="python"
        )
        self.assertNotIn(LOW_CONFIDENCE, flags)
        self.assertNotIn(NEEDS_HUMAN_REVIEW, flags)
        self.assertFalse(awaiting)

    def test_custom_threshold_overrides_default(self) -> None:
        env = _envelope([_crit(confidence=0.7)])
        flags, awaiting = compute_review_flags(
            env,
            retrieval_status="ok",
            language="python",
            low_confidence_threshold=0.8,
        )
        self.assertIn(LOW_CONFIDENCE, flags)
        self.assertTrue(awaiting)

    def test_missing_or_non_numeric_confidence_is_ignored(self) -> None:
        env = _envelope(
            [
                {"name": "C", "score": 80, "level": "Proficient", "justification": "ok"},
                {"name": "D", "score": 80, "level": "Proficient", "justification": "ok",
                 "confidence": "high"},
            ]
        )
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="python"
        )
        self.assertNotIn(LOW_CONFIDENCE, flags)
        self.assertFalse(awaiting)


class RagNoMatchTriggerTests(unittest.TestCase):
    def test_no_match_triggers_review(self) -> None:
        env = _envelope([_crit(confidence=0.95)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="no_match", language="python"
        )
        self.assertIn(NO_MATCH, flags)
        self.assertIn(NEEDS_HUMAN_REVIEW, flags)
        self.assertTrue(awaiting)

    def test_unavailable_does_not_trigger_review(self) -> None:
        env = _envelope([_crit(confidence=0.95)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="unavailable", language="python"
        )
        self.assertNotIn(NO_MATCH, flags)
        self.assertNotIn(NEEDS_HUMAN_REVIEW, flags)
        self.assertFalse(awaiting)

    def test_ok_status_does_not_trigger(self) -> None:
        env = _envelope([_crit(confidence=0.95)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="python"
        )
        self.assertNotIn(NEEDS_HUMAN_REVIEW, flags)
        self.assertFalse(awaiting)


class UnsupportedLanguageTriggerTests(unittest.TestCase):
    def test_language_outside_supported_set_triggers(self) -> None:
        env = _envelope([_crit(confidence=0.95)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="rust"
        )
        self.assertIn(UNSUPPORTED_LANGUAGE, flags)
        self.assertIn(NEEDS_HUMAN_REVIEW, flags)
        self.assertTrue(awaiting)

    def test_supported_language_case_insensitive(self) -> None:
        env = _envelope([_crit(confidence=0.95)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language="Python"
        )
        self.assertNotIn(UNSUPPORTED_LANGUAGE, flags)
        self.assertFalse(awaiting)

    def test_none_language_does_not_trigger(self) -> None:
        env = _envelope([_crit(confidence=0.95)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="ok", language=None
        )
        self.assertNotIn(UNSUPPORTED_LANGUAGE, flags)
        self.assertFalse(awaiting)

    def test_custom_supported_set_overrides_default(self) -> None:
        env = _envelope([_crit(confidence=0.95)])
        flags, _ = compute_review_flags(
            env,
            retrieval_status="ok",
            language="rust",
            supported_languages=("python", "rust"),
        )
        self.assertNotIn(UNSUPPORTED_LANGUAGE, flags)


class CompoundTriggerTests(unittest.TestCase):
    def test_multiple_triggers_collapse_to_single_needs_human_review(self) -> None:
        env = _envelope([_crit(confidence=0.4, level=NEEDS_HUMAN_REVIEW)])
        flags, awaiting = compute_review_flags(
            env, retrieval_status="no_match", language="rust"
        )
        self.assertEqual(flags.count(NEEDS_HUMAN_REVIEW), 1)
        self.assertIn(LOW_CONFIDENCE, flags)
        self.assertIn(NO_MATCH, flags)
        self.assertIn(UNSUPPORTED_LANGUAGE, flags)
        self.assertTrue(awaiting)
        self.assertEqual(determine_terminal_status(awaiting), "Awaiting Review")


class DetermineTerminalStatusTests(unittest.TestCase):
    def test_awaiting_review_when_true(self) -> None:
        self.assertEqual(determine_terminal_status(True), "Awaiting Review")

    def test_completed_when_false(self) -> None:
        self.assertEqual(determine_terminal_status(False), "Completed")


if __name__ == "__main__":
    unittest.main()
