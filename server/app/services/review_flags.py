"""Pure helpers that compute the post-Pass-3 review flags.

Per ``docs/milestones/milestone-03-tasks.md`` task #14 and
``docs/design-doc.md`` §4 / §3 §II, the pipeline must set
``NEEDS_HUMAN_REVIEW`` on the final envelope's ``flags`` array when
*any* of the following hold:

  (a) The model marked a criterion as ``NEEDS_HUMAN_REVIEW`` (ambiguous
      rubric language).
  (b) Any criterion's ``confidence`` is below a configurable threshold.
  (c) RAG retrieval returned ``retrieval_status: "no_match"`` (no
      style chunk above the 0.75 cosine threshold).
  (d) The detected language is not on the supported style-guide list.

When the flag is set, the submission terminates as ``Awaiting Review``
instead of ``Completed``.

This module is intentionally **DB-free, IO-free, and side-effect-free**
so it can be unit-tested in isolation and reused from the pipeline,
the API layer, or future audit tooling.
"""

from __future__ import annotations

from typing import Iterable

# ---------------------------------------------------------------------------
# Tunable constants (module-level — overridable per-call)
# ---------------------------------------------------------------------------

# Confidence below this threshold on any criterion triggers
# ``NEEDS_HUMAN_REVIEW``.  0.6 chosen as a conservative default that
# still admits "Proficient with caveats"; production may override.
DEFAULT_LOW_CONFIDENCE_THRESHOLD: float = 0.6

# Languages with curated style-guide RAG corpora per design-doc §3 §II.
# Anything outside this set triggers ``NEEDS_HUMAN_REVIEW`` so the
# instructor can supply a style guide URL before linting proceeds.
SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
)

NEEDS_HUMAN_REVIEW: str = "NEEDS_HUMAN_REVIEW"
LOW_CONFIDENCE: str = "LOW_CONFIDENCE"
NO_MATCH: str = "no_match"
UNSUPPORTED_LANGUAGE: str = "unsupported_language"


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------


def compute_review_flags(
    envelope: dict,
    *,
    retrieval_status: str | None = None,
    language: str | None = None,
    supported_languages: Iterable[str] = SUPPORTED_LANGUAGES,
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
) -> tuple[list[str], bool]:
    """Augment an envelope's flag set with ``NEEDS_HUMAN_REVIEW`` triggers.

    Args:
        envelope: A MAPLE Standard Response Envelope dict.  Typically
            the output of :func:`app.services.ai_passes.run_pass3`.
            Only ``criteria_scores`` and ``flags`` are read; the dict
            is **not** mutated.
        retrieval_status: Pass 2's ``retrieval_status`` value
            (``"ok" | "no_match" | "unavailable" | None``).
        language: Detected primary language (e.g. ``"python"``).
        supported_languages: Iterable of languages with curated style
            guides.  Defaults to the design-doc §3 §II list.
        low_confidence_threshold: Confidences strictly below this
            value flip ``NEEDS_HUMAN_REVIEW`` on.

    Returns:
        ``(flags, awaiting_review)`` where ``flags`` is the augmented
        flag list (existing flags preserved, no duplicates) and
        ``awaiting_review`` is ``True`` iff the resulting flag set
        contains ``NEEDS_HUMAN_REVIEW``.
    """
    flags: list[str] = list(envelope.get("flags", []) or [])
    supported = {s.lower() for s in supported_languages}

    triggers_human_review = False

    # (a) Ambiguous rubric language — model marked a criterion
    #     NEEDS_HUMAN_REVIEW or already raised the envelope flag.
    if NEEDS_HUMAN_REVIEW in flags:
        triggers_human_review = True
    if any(
        (c.get("level") == NEEDS_HUMAN_REVIEW)
        for c in envelope.get("criteria_scores", []) or []
    ):
        triggers_human_review = True

    # (b) Low confidence on any criterion.
    if _has_low_confidence(envelope, low_confidence_threshold):
        triggers_human_review = True
        if LOW_CONFIDENCE not in flags:
            flags.append(LOW_CONFIDENCE)

    # (c) RAG returned no match.  ``"unavailable"`` (retriever not
    #     wired) is treated as best-effort and does NOT trigger review
    #     by itself — the orchestrator can decide separately.
    if retrieval_status == "no_match":
        triggers_human_review = True
        if NO_MATCH not in flags:
            flags.append(NO_MATCH)

    # (d) Unsupported language (no curated style guide).
    if language is not None and language.lower() not in supported:
        triggers_human_review = True
        if UNSUPPORTED_LANGUAGE not in flags:
            flags.append(UNSUPPORTED_LANGUAGE)

    if triggers_human_review and NEEDS_HUMAN_REVIEW not in flags:
        flags.append(NEEDS_HUMAN_REVIEW)

    awaiting_review = NEEDS_HUMAN_REVIEW in flags
    return flags, awaiting_review


def determine_terminal_status(awaiting_review: bool) -> str:
    """Map the review-flag verdict to a submission terminal status.

    Convenience helper so the pipeline does not have to repeat the
    string literals.  Status values match
    :mod:`app.models.submission`.
    """
    return "Awaiting Review" if awaiting_review else "Completed"


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _has_low_confidence(envelope: dict, threshold: float) -> bool:
    for criterion in envelope.get("criteria_scores", []) or []:
        confidence = criterion.get("confidence")
        if isinstance(confidence, (int, float)) and confidence < threshold:
            return True
    return False


__all__ = [
    "DEFAULT_LOW_CONFIDENCE_THRESHOLD",
    "LOW_CONFIDENCE",
    "NEEDS_HUMAN_REVIEW",
    "NO_MATCH",
    "SUPPORTED_LANGUAGES",
    "UNSUPPORTED_LANGUAGE",
    "compute_review_flags",
    "determine_terminal_status",
]
