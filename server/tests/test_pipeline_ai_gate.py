"""Regression tests for the AI-phase activation gate in ``run_pipeline``.

These tests pin two contracts that were silently broken before, causing
GitHub submissions to land at ``Completed`` with no AI analysis:

1. The implemented :func:`app.services.llm.complete` MUST satisfy
   :func:`app.services.pipeline._is_llm_ready` so the AI phase is
   actually entered. Specifically, ``complete`` must accept a ``model``
   kwarg (or ``**kwargs``) and must not be the M1 ``raise
   NotImplementedError`` stub.

2. ``run_pipeline`` MUST NOT mark a submission ``Completed`` between
   the deterministic phase and the AI phase. A transient ``Completed``
   would let the frontend's terminal-status guard short-circuit polling
   before ``ai_feedback_json`` lands (status-page.component.ts).
"""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import llm
from app.services.pipeline import _is_llm_ready, run_pipeline


_PYTEST_ALL_PASS_STDOUT = (
    "============================= test session starts ==============================\n"
    "platform linux -- Python 3.12, pytest-8.0.0\n"
    "collected 2 items\n\n"
    "tests/test_basic.py::test_one PASSED\n"
    "tests/test_basic.py::test_two PASSED\n\n"
    "============================== 2 passed in 0.10s ===============================\n"
)


class IsLlmReadyContractTests(unittest.TestCase):
    """``_is_llm_ready`` must return True for the real ``llm.complete``."""

    def test_complete_accepts_model_kwarg(self) -> None:
        sig = inspect.signature(llm.complete)
        has_var_kw = any(
            p.kind is inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
        self.assertTrue(
            "model" in sig.parameters or has_var_kw,
            "llm.complete must accept a 'model' kwarg or **kwargs so the "
            "pipeline readiness gate (_is_llm_ready) opens.",
        )

    def test_complete_is_not_the_m1_not_implemented_stub(self) -> None:
        src = inspect.getsource(llm.complete)
        self.assertNotIn(
            "raise NotImplementedError",
            src,
            "llm.complete is still the M1 stub; the AI phase will be skipped.",
        )

    def test_is_llm_ready_returns_true_for_implemented_complete(self) -> None:
        self.assertTrue(_is_llm_ready())


class _PipelineHarness:
    """Minimal patch stack for exercising :func:`run_pipeline`."""

    @staticmethod
    def patches(
        *,
        status_calls: list[str],
        update_eval_mock: AsyncMock,
        llm_ready: bool = True,
    ):
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        mock_db.add = MagicMock()

        class _CM:
            async def __aenter__(self):
                return mock_db

            async def __aexit__(self, *args):
                return None

        async def track_status(_db, _sid, status):
            status_calls.append(status)
            return MagicMock()

        assignment = MagicMock()
        assignment.test_suite_repo_url = "https://github.com/org/tests.git"
        assignment.language_override = None
        assignment.enable_lint_review = False

        from app.services.docker_client import ContainerResult

        return [
            patch(
                "app.services.pipeline.async_session_maker",
                return_value=_CM(),
            ),
            patch(
                "app.services.pipeline.update_submission_status",
                new=AsyncMock(side_effect=track_status),
            ),
            patch(
                "app.services.pipeline.get_assignment_by_id",
                new=AsyncMock(return_value=assignment),
            ),
            patch(
                "app.services.pipeline.run_container",
                new=AsyncMock(
                    return_value=ContainerResult(
                        stdout=_PYTEST_ALL_PASS_STDOUT,
                        stderr="",
                        exit_code=0,
                    )
                ),
            ),
            patch(
                "app.services.pipeline.persist_evaluation_result",
                new=AsyncMock(),
            ),
            patch(
                "app.services.pipeline.update_evaluation_result",
                new=update_eval_mock,
            ),
            patch(
                "app.main.clone_repository",
                new=AsyncMock(return_value="deadbeef"),
            ),
            patch(
                "app.services.pipeline.detect_language_version",
                return_value={"language": "python", "version": "3.12", "source": "pyproject.toml", "override_applied": False},
            ),
            patch(
                "app.services.pipeline._is_llm_ready",
                return_value=llm_ready,
            ),
        ]


class NoTransientCompletedStatusTests(unittest.TestCase):
    """The pipeline must not mark ``Completed`` mid-flight when AI runs.

    A transient ``Completed`` (between deterministic and AI phases) is
    indistinguishable from a real terminal ``Completed`` to the
    frontend, which then stops polling and the user never sees AI
    analysis even though the backend later persists it.
    """

    @staticmethod
    def _valid_envelope() -> dict:
        return {
            "criteria_scores": [
                {
                    "name": "Correctness",
                    "score": 90,
                    "level": "STRONG",
                    "justification": "ok",
                    "confidence": 0.9,
                }
            ],
            "deterministic_score": 100.0,
            "metadata": {},
            "flags": [],
        }

    def test_status_skips_transient_completed_when_ai_runs(self) -> None:
        async def _run() -> None:
            status_calls: list[str] = []
            update_eval_mock = AsyncMock()
            envelope = self._valid_envelope()
            pass1_result = {"pass": "pass1", "failures": [], "summary": "ok"}
            reasoning = {
                "pass1": pass1_result,
                "pass2": {"skipped": True, "reason": "no_lint_no_rubric"},
            }

            patches = _PipelineHarness.patches(
                status_calls=status_calls,
                update_eval_mock=update_eval_mock,
                llm_ready=True,
            )

            with contextlib.ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)
                stack.enter_context(
                    patch(
                        "app.services.pipeline.run_pass1",
                        new=AsyncMock(return_value=pass1_result),
                    )
                )
                stack.enter_context(
                    patch(
                        "app.services.pipeline.run_pass2",
                        new=AsyncMock(return_value=reasoning),
                    )
                )
                stack.enter_context(
                    patch(
                        "app.services.pipeline.run_pass3",
                        new=AsyncMock(return_value=envelope),
                    )
                )
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        uuid.uuid4(),
                        uuid.uuid4(),
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            self.assertEqual(
                status_calls,
                ["Testing", "Evaluating", "Completed"],
                "AI phase must transition Testing -> Evaluating -> "
                "<terminal>; the early Completed caused the frontend "
                "polling guard to short-circuit before ai_feedback_json "
                "was persisted.",
            )
            update_eval_mock.assert_awaited_once()
            kwargs = update_eval_mock.await_args.kwargs
            self.assertIs(kwargs["ai_feedback_json"], envelope)

        asyncio.run(_run())

    def test_status_marks_completed_only_when_ai_skipped(self) -> None:
        async def _run() -> None:
            status_calls: list[str] = []
            update_eval_mock = AsyncMock()
            patches = _PipelineHarness.patches(
                status_calls=status_calls,
                update_eval_mock=update_eval_mock,
                llm_ready=False,
            )

            with contextlib.ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        uuid.uuid4(),
                        uuid.uuid4(),
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            self.assertEqual(status_calls, ["Testing", "Completed"])
            update_eval_mock.assert_not_awaited()

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
