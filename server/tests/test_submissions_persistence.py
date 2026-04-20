"""Focused async tests for the M3 submissions persistence helpers.

Covers:

* :func:`persist_evaluation_result` accepting the optional
  ``ai_feedback_json`` parameter (M2 backwards compatibility).
* :func:`update_evaluation_result` merge-update semantics, including
  the load-by-submission_id contract and the
  ``DuplicateEvaluationError`` race fallback.

Following the project's established test pattern (see
``test_pipeline.py``), these tests use ``AsyncMock`` + ``MagicMock``
to drive the SQLAlchemy ``AsyncSession`` interface rather than spinning
up an in-memory SQLite database.  This keeps the suite hermetic (no
extra deps) while still exercising every observable branch of the
helpers under test.
"""

from __future__ import annotations

import asyncio
import unittest
import uuid
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.exc import IntegrityError

from app.services.submissions import (
    DuplicateEvaluationError,
    persist_evaluation_result,
    update_evaluation_result,
)


_SID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


def _scalar_result(value):
    """Build a fake SQLAlchemy Result whose ``scalar_one_or_none`` returns *value*."""
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _fresh_db(*, execute_side_effects=None):
    """Build a fresh AsyncSession-shaped mock.

    ``execute_side_effects`` is an optional iterable of values returned
    in order from successive ``await db.execute(...)`` calls — used to
    simulate the load-then-reload sequence in the race fallback.
    """
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    if execute_side_effects is not None:
        db.execute = AsyncMock(side_effect=list(execute_side_effects))
    else:
        db.execute = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# persist_evaluation_result — M2 backward compatibility + AI payload accept
# ---------------------------------------------------------------------------


class PersistEvaluationResultM3Tests(unittest.TestCase):
    def test_default_ai_feedback_json_is_none_for_m2_callers(self) -> None:
        """An M2 caller that omits ai_feedback_json must still succeed,
        and the persisted row must carry ``ai_feedback_json=None``."""

        async def _run() -> None:
            db = _fresh_db()
            await persist_evaluation_result(
                db,
                submission_id=_SID,
                deterministic_score=88.0,
                metadata_json={"language": {"language": "python"}},
            )
            db.add.assert_called_once()
            persisted = db.add.call_args.args[0]
            self.assertIsNone(persisted.ai_feedback_json)
            self.assertEqual(persisted.deterministic_score, 88.0)
            self.assertEqual(
                persisted.metadata_json, {"language": {"language": "python"}}
            )
            db.commit.assert_awaited_once()
            db.refresh.assert_awaited_once_with(persisted)

        asyncio.run(_run())

    def test_accepts_ai_feedback_json_kwarg_when_supplied(self) -> None:
        """M3 callers may pre-populate ai_feedback_json at insert time."""

        async def _run() -> None:
            db = _fresh_db()
            envelope = {"pass": "pass3", "criteria_scores": [], "flags": []}
            await persist_evaluation_result(
                db,
                submission_id=_SID,
                deterministic_score=72.5,
                metadata_json={"language": {"language": "python"}},
                ai_feedback_json=envelope,
            )
            persisted = db.add.call_args.args[0]
            self.assertEqual(persisted.ai_feedback_json, envelope)

        asyncio.run(_run())

    def test_integrity_error_still_raises_duplicate_evaluation_error(
        self,
    ) -> None:
        """Adding ai_feedback_json must not regress the dedup contract."""

        async def _run() -> None:
            db = _fresh_db()
            db.commit = AsyncMock(
                side_effect=IntegrityError("dup", params=None, orig=Exception())
            )
            with self.assertRaises(DuplicateEvaluationError):
                await persist_evaluation_result(
                    db,
                    submission_id=_SID,
                    deterministic_score=90.0,
                    ai_feedback_json={"pass": "pass3"},
                )
            db.rollback.assert_awaited_once()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# update_evaluation_result — merge / insert / race fallback
# ---------------------------------------------------------------------------


class UpdateEvaluationResultMergeTests(unittest.TestCase):
    """Exercise the load-by-submission_id + merge contract."""

    def test_loads_existing_row_and_merges_both_fields(self) -> None:
        async def _run() -> None:
            existing = MagicMock()
            existing.ai_feedback_json = None
            existing.metadata_json = {"language": {"language": "python"}}

            db = _fresh_db(execute_side_effects=[_scalar_result(existing)])
            envelope = {"pass": "pass3", "flags": ["NEEDS_HUMAN_REVIEW"]}
            new_meta = {
                "language": {"language": "python"},
                "style_guide_version": "2024-05",
            }

            result = await update_evaluation_result(
                db,
                submission_id=_SID,
                ai_feedback_json=envelope,
                metadata_json=new_meta,
            )

            self.assertIs(result, existing)
            self.assertEqual(existing.ai_feedback_json, envelope)
            self.assertEqual(existing.metadata_json, new_meta)
            db.add.assert_not_called()
            db.commit.assert_awaited_once()
            db.refresh.assert_awaited_once_with(existing)

        asyncio.run(_run())

    def test_none_fields_leave_existing_columns_untouched(self) -> None:
        """Partial updates: passing ``None`` skips that column."""

        async def _run() -> None:
            existing = MagicMock()
            existing.ai_feedback_json = {"pass": "pass3", "preserved": True}
            existing.metadata_json = {"language": {"language": "python"}}

            db = _fresh_db(execute_side_effects=[_scalar_result(existing)])

            await update_evaluation_result(
                db,
                submission_id=_SID,
                ai_feedback_json=None,
                metadata_json={"style_guide_version": "2024-05"},
            )

            # ai_feedback_json untouched; metadata_json overwritten.
            self.assertEqual(
                existing.ai_feedback_json, {"pass": "pass3", "preserved": True}
            )
            self.assertEqual(
                existing.metadata_json, {"style_guide_version": "2024-05"}
            )

        asyncio.run(_run())

    def test_inserts_new_row_when_no_existing_evaluation_result(self) -> None:
        """Replay / tooling path: no existing row → insert fresh."""

        async def _run() -> None:
            db = _fresh_db(execute_side_effects=[_scalar_result(None)])
            envelope = {"pass": "pass3", "criteria_scores": [], "flags": []}

            result = await update_evaluation_result(
                db,
                submission_id=_SID,
                ai_feedback_json=envelope,
                metadata_json={"language": {"language": "python"}},
            )

            db.add.assert_called_once()
            inserted = db.add.call_args.args[0]
            self.assertEqual(inserted.submission_id, _SID)
            self.assertEqual(inserted.ai_feedback_json, envelope)
            self.assertIsNone(inserted.deterministic_score)
            db.commit.assert_awaited_once()
            db.refresh.assert_awaited_once_with(inserted)
            self.assertIs(result, inserted)

        asyncio.run(_run())

    def test_concurrent_insert_race_falls_back_to_merge_update(self) -> None:
        """Race fallback: insert hits IntegrityError → reload → merge.

        This is the explicit
        ``Respect DuplicateEvaluationError behavior`` requirement: the
        AI update path never surfaces a duplicate to the caller.
        """

        async def _run() -> None:
            # Concurrent writer landed between our SELECT and INSERT.
            raced_row = MagicMock()
            raced_row.ai_feedback_json = {"pass": "pass3", "from": "racer"}
            raced_row.metadata_json = {"language": {"language": "python"}}

            db = _fresh_db(
                execute_side_effects=[
                    _scalar_result(None),       # initial load: empty
                    _scalar_result(raced_row),  # post-rollback reload: present
                ]
            )
            db.commit = AsyncMock(
                side_effect=[
                    IntegrityError("dup", params=None, orig=Exception()),
                    None,  # second commit (merge-update) succeeds
                ]
            )

            our_envelope = {"pass": "pass3", "from": "us"}
            result = await update_evaluation_result(
                db,
                submission_id=_SID,
                ai_feedback_json=our_envelope,
                metadata_json={"style_guide_version": "2024-05"},
            )

            # Must NOT propagate DuplicateEvaluationError to the caller.
            db.rollback.assert_awaited_once()
            self.assertIs(result, raced_row)
            # Our payload wins on the merge step.
            self.assertEqual(raced_row.ai_feedback_json, our_envelope)
            self.assertEqual(
                raced_row.metadata_json, {"style_guide_version": "2024-05"}
            )
            # Two execute() calls: load + reload.
            self.assertEqual(db.execute.await_count, 2)
            # Two commit() calls: failed insert + successful merge.
            self.assertEqual(db.commit.await_count, 2)

        asyncio.run(_run())

    def test_returns_none_when_post_rollback_reload_still_empty(self) -> None:
        """Defence-in-depth: corrupt DB state (rollback then reload still
        returns ``None``) → return ``None`` rather than crashing."""

        async def _run() -> None:
            db = _fresh_db(
                execute_side_effects=[
                    _scalar_result(None),  # initial load: empty
                    _scalar_result(None),  # post-rollback reload: still empty
                ]
            )
            db.commit = AsyncMock(
                side_effect=IntegrityError("dup", params=None, orig=Exception())
            )

            result = await update_evaluation_result(
                db,
                submission_id=_SID,
                ai_feedback_json={"pass": "pass3"},
            )

            self.assertIsNone(result)
            db.rollback.assert_awaited_once()

        asyncio.run(_run())

    def test_does_not_raise_duplicate_evaluation_error_to_caller(self) -> None:
        """The C3 contract: AI update path swallows DuplicateEvaluationError
        and converges on the canonical row instead of re-raising."""

        async def _run() -> None:
            raced_row = MagicMock()
            raced_row.ai_feedback_json = None
            raced_row.metadata_json = None

            db = _fresh_db(
                execute_side_effects=[
                    _scalar_result(None),
                    _scalar_result(raced_row),
                ]
            )
            db.commit = AsyncMock(
                side_effect=[
                    IntegrityError("dup", params=None, orig=Exception()),
                    None,
                ]
            )

            # Should NOT raise.
            await update_evaluation_result(
                db,
                submission_id=_SID,
                ai_feedback_json={"pass": "pass3"},
            )

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
