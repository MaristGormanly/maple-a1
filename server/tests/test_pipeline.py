import asyncio
import contextlib
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.docker_client import ContainerResult
from app.services.pipeline import run_pipeline


MOCK_SUBMISSION_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
MOCK_ASSIGNMENT_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")

PYTEST_ALL_PASS_STDOUT = (
    "============================= test session starts ==============================\n"
    "collected 2 items\n\n"
    "test_example.py::test_one PASSED\n"
    "test_example.py::test_two PASSED\n\n"
    "============================== 2 passed in 0.03s ==============================\n"
)

PYTEST_FAIL_STDOUT = (
    "============================= test session starts ==============================\n"
    "collected 2 items\n\n"
    "test_example.py::test_one PASSED\n"
    "test_example.py::test_two FAILED\n\n"
    "============================== 1 failed, 1 passed in 0.04s ==============================\n"
)

FAKE_LANGUAGE = {
    "language": "python",
    "version": "3.12",
    "source": "pyproject.toml",
    "override_applied": False,
}


def _fake_assignment(
    suite_url: str | None = "https://github.com/org/tests.git",
    enable_lint_review: bool = False,
):
    a = MagicMock()
    a.test_suite_repo_url = suite_url
    a.language_override = None
    a.enable_lint_review = enable_lint_review
    return a


class PipelineTests(unittest.TestCase):
    def test_run_pipeline_returns_immediately_when_assignment_id_none(self) -> None:
        async def _run() -> None:
            with patch(
                "app.services.pipeline.run_container",
                new=AsyncMock(),
            ) as docker_mock:
                await run_pipeline(
                    MOCK_SUBMISSION_ID,
                    None,
                    "/tmp/student",
                    {"rubric": True},
                    "pat",
                )
                docker_mock.assert_not_called()

        asyncio.run(_run())

    def test_run_pipeline_success_status_and_persist(self) -> None:
        async def _run() -> None:
            mock_db = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.add = MagicMock()

            class _CM:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *args):
                    return None

            status_calls: list[str] = []

            async def track_status(db, sid, status):
                status_calls.append(status)
                return MagicMock()

            container_result = ContainerResult(
                stdout=PYTEST_ALL_PASS_STDOUT, stderr="", exit_code=0
            )

            with (
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
                    new=AsyncMock(return_value=_fake_assignment()),
                ),
                patch(
                    "app.services.pipeline.run_container",
                    new=AsyncMock(return_value=container_result),
                ),
                patch(
                    "app.services.pipeline.persist_evaluation_result",
                    new=AsyncMock(),
                ) as persist_mock,
                patch(
                    "app.main.clone_repository",
                    new=AsyncMock(return_value="deadbeef"),
                ) as clone_mock,
                patch(
                    "app.services.pipeline.detect_language_version",
                    return_value=FAKE_LANGUAGE,
                ),
            ):
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            self.assertEqual(status_calls, ["Testing", "Completed"])
            clone_mock.assert_awaited_once()
            call_kw = clone_mock.await_args
            self.assertEqual(
                call_kw[0][0], "https://github.com/org/tests.git"
            )
            persist_mock.assert_awaited_once()
            kwargs = persist_mock.await_args.kwargs
            self.assertEqual(kwargs["submission_id"], MOCK_SUBMISSION_ID)
            self.assertEqual(kwargs["deterministic_score"], 100.0)

            meta = kwargs["metadata_json"]
            self.assertEqual(meta["language"], FAKE_LANGUAGE)
            self.assertEqual(meta["exit_code"], 0)
            self.assertIn("resource_constraint_metadata", meta)
            ts = meta["test_summary"]
            self.assertEqual(ts["passed"], 2)
            self.assertEqual(ts["failed"], 0)
            self.assertEqual(ts["errors"], 0)
            self.assertEqual(ts["framework"], "pytest")

        asyncio.run(_run())

    def test_run_pipeline_completes_with_zero_score_when_tests_fail(self) -> None:
        async def _run() -> None:
            mock_db = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()

            class _CM:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *args):
                    return None

            status_calls: list[str] = []

            async def track_status(db, sid, status):
                status_calls.append(status)
                return MagicMock()

            with (
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
                    new=AsyncMock(return_value=_fake_assignment()),
                ),
                patch(
                    "app.services.pipeline.run_container",
                    new=AsyncMock(
                        return_value=ContainerResult(
                            stdout=PYTEST_FAIL_STDOUT,
                            stderr="",
                            exit_code=1,
                        )
                    ),
                ),
                patch(
                    "app.services.pipeline.persist_evaluation_result",
                    new=AsyncMock(),
                ) as persist_mock,
                patch(
                    "app.main.clone_repository",
                    new=AsyncMock(return_value="abc"),
                ),
                patch(
                    "app.services.pipeline.detect_language_version",
                    return_value=FAKE_LANGUAGE,
                ),
            ):
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {},
                        "pat",
                    )

            self.assertEqual(status_calls, ["Testing", "Completed"])
            self.assertEqual(
                persist_mock.await_args.kwargs["deterministic_score"], 50.0
            )
            meta = persist_mock.await_args.kwargs["metadata_json"]
            self.assertEqual(meta["exit_code"], 1)
            self.assertEqual(meta["test_summary"]["passed"], 1)
            self.assertEqual(meta["test_summary"]["failed"], 1)

        asyncio.run(_run())

    def test_run_pipeline_marks_failed_when_clone_raises(self) -> None:
        async def _run() -> None:
            mock_db = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()

            class _CM:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *args):
                    return None

            status_calls: list[str] = []

            async def track_status(db, sid, status):
                status_calls.append(status)
                return MagicMock()

            with (
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
                    new=AsyncMock(return_value=_fake_assignment()),
                ),
                patch(
                    "app.services.pipeline.run_container",
                    new=AsyncMock(),
                ) as docker_mock,
                patch(
                    "app.main.clone_repository",
                    new=AsyncMock(side_effect=RuntimeError("clone failed")),
                ),
                patch("app.services.pipeline.logger.exception"),
            ):
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {},
                        "pat",
                    )

            self.assertEqual(status_calls, ["Testing", "Failed"])
            docker_mock.assert_not_called()

        asyncio.run(_run())

    def test_run_pipeline_no_clone_when_test_suite_url_missing(self) -> None:
        async def _run() -> None:
            mock_db = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()

            class _CM:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *args):
                    return None

            status_calls: list[str] = []

            async def track_status(db, sid, status):
                status_calls.append(status)
                return MagicMock()

            with (
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
                    new=AsyncMock(return_value=_fake_assignment(suite_url=None)),
                ),
                patch(
                    "app.services.pipeline.run_container",
                    new=AsyncMock(),
                ) as docker_mock,
                patch(
                    "app.main.clone_repository",
                    new=AsyncMock(),
                ) as clone_mock,
            ):
                await run_pipeline(
                    MOCK_SUBMISSION_ID,
                    MOCK_ASSIGNMENT_ID,
                    "/tmp/student",
                    {},
                    "pat",
                )

            self.assertEqual(status_calls, ["Testing", "Failed"])
            clone_mock.assert_not_called()
            docker_mock.assert_not_called()

        asyncio.run(_run())


    def test_run_pipeline_stays_completed_on_duplicate_evaluation(self) -> None:
        """A duplicate EvaluationResult must not transition the submission to Failed."""

        async def _run() -> None:
            mock_db = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()
            mock_db.add = MagicMock()

            class _CM:
                async def __aenter__(self):
                    return mock_db

                async def __aexit__(self, *args):
                    return None

            status_calls: list[str] = []

            async def track_status(db, sid, status):
                status_calls.append(status)
                return MagicMock()

            container_result = ContainerResult(
                stdout=PYTEST_ALL_PASS_STDOUT, stderr="", exit_code=0
            )

            from app.services.submissions import DuplicateEvaluationError

            with (
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
                    new=AsyncMock(return_value=_fake_assignment()),
                ),
                patch(
                    "app.services.pipeline.run_container",
                    new=AsyncMock(return_value=container_result),
                ),
                patch(
                    "app.services.pipeline.persist_evaluation_result",
                    new=AsyncMock(
                        side_effect=DuplicateEvaluationError("already exists"),
                    ),
                ),
                patch(
                    "app.main.clone_repository",
                    new=AsyncMock(return_value="deadbeef"),
                ),
                patch(
                    "app.services.pipeline.detect_language_version",
                    return_value=FAKE_LANGUAGE,
                ),
            ):
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            self.assertEqual(status_calls, ["Testing"])
            self.assertNotIn("Failed", status_calls)

        asyncio.run(_run())


class PersistEvaluationResultTests(unittest.TestCase):
    """Pin the idempotency contract of persist_evaluation_result."""

    def test_raises_duplicate_evaluation_error_on_integrity_violation(self) -> None:
        from sqlalchemy.exc import IntegrityError
        from app.services.submissions import (
            DuplicateEvaluationError,
            persist_evaluation_result,
        )

        async def _run() -> None:
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock(
                side_effect=IntegrityError("dup", params=None, orig=Exception())
            )
            mock_db.rollback = AsyncMock()

            with self.assertRaises(DuplicateEvaluationError):
                await persist_evaluation_result(
                    mock_db,
                    submission_id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
                    deterministic_score=90.0,
                )

            mock_db.rollback.assert_awaited_once()

        asyncio.run(_run())

    def test_succeeds_when_no_conflict(self) -> None:
        from app.services.submissions import persist_evaluation_result

        async def _run() -> None:
            mock_db = MagicMock()
            mock_db.add = MagicMock()
            mock_db.commit = AsyncMock()
            mock_db.refresh = AsyncMock()

            result = await persist_evaluation_result(
                mock_db,
                submission_id=uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
                deterministic_score=75.0,
                metadata_json={"language": {"language": "python"}},
            )

            mock_db.add.assert_called_once()
            mock_db.commit.assert_awaited_once()
            mock_db.refresh.assert_awaited_once()
            self.assertIsNotNone(result)

        asyncio.run(_run())


class M3EvaluatingPhaseTests(unittest.TestCase):
    """Pipeline tests for the Milestone 3 ``Evaluating`` phase wiring.

    Each test forces ``_is_llm_ready`` to ``True`` and patches the
    three pass functions + persistence helpers so the phase runs
    deterministically without touching Jayden's LLM stub.
    """

    @staticmethod
    def _patch_stack(
        *,
        status_calls: list[str],
        persist_mock: AsyncMock,
        update_eval_mock: AsyncMock,
        container_stdout: str = PYTEST_ALL_PASS_STDOUT,
        container_exit: int = 0,
        assignment=None,
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

        async def track_status(db, sid, status):
            status_calls.append(status)
            return MagicMock()

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
                new=AsyncMock(return_value=assignment or _fake_assignment()),
            ),
            patch(
                "app.services.pipeline.run_container",
                new=AsyncMock(
                    return_value=ContainerResult(
                        stdout=container_stdout,
                        stderr="",
                        exit_code=container_exit,
                    )
                ),
            ),
            patch(
                "app.services.pipeline.persist_evaluation_result",
                new=persist_mock,
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
                return_value=FAKE_LANGUAGE,
            ),
            patch(
                "app.services.pipeline._is_llm_ready",
                return_value=llm_ready,
            ),
        ]

    @staticmethod
    def _valid_envelope(
        flags: list[str] | None = None,
        confidence: float = 0.95,
    ) -> dict:
        return {
            "pass": "pass3",
            "criteria_scores": [
                {
                    "criterion_name": "Correctness",
                    "score": 90,
                    "level": "MEETS",
                    "justification": "All tests passed.",
                    "confidence": confidence,
                }
            ],
            "deterministic_score": 100.0,
            "metadata": {},
            "flags": list(flags or []),
        }

    @staticmethod
    def _enter_all(stack: contextlib.ExitStack, patches: list) -> None:
        for p in patches:
            stack.enter_context(p)

    def test_evaluating_phase_runs_when_llm_ready_and_marks_completed(
        self,
    ) -> None:
        async def _run() -> None:
            status_calls: list[str] = []
            persist_mock = AsyncMock()
            update_eval_mock = AsyncMock()

            pass1_result = {"pass": "pass1", "failures": [], "summary": "ok"}
            reasoning_after_pass2 = {
                "pass1": pass1_result,
                "pass2": {"skipped": True, "reason": "no_lint_no_rubric"},
            }
            envelope = self._valid_envelope()

            patches = self._patch_stack(
                status_calls=status_calls,
                persist_mock=persist_mock,
                update_eval_mock=update_eval_mock,
            )

            p1_mock = AsyncMock(return_value=pass1_result)
            p2_mock = AsyncMock(return_value=reasoning_after_pass2)
            p3_mock = AsyncMock(return_value=envelope)

            with contextlib.ExitStack() as stack:
                self._enter_all(stack, patches)
                stack.enter_context(
                    patch("app.services.pipeline.run_pass1", new=p1_mock)
                )
                stack.enter_context(
                    patch("app.services.pipeline.run_pass2", new=p2_mock)
                )
                stack.enter_context(
                    patch("app.services.pipeline.run_pass3", new=p3_mock)
                )
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            self.assertEqual(
                status_calls,
                ["Testing", "Completed", "Evaluating", "Completed"],
            )
            p1_mock.assert_awaited_once()
            p2_mock.assert_awaited_once()
            p3_mock.assert_awaited_once()
            update_eval_mock.assert_awaited_once()
            kwargs = update_eval_mock.await_args.kwargs
            self.assertEqual(kwargs["submission_id"], MOCK_SUBMISSION_ID)
            self.assertIs(kwargs["ai_feedback_json"], envelope)

        asyncio.run(_run())

    def test_evaluating_phase_skipped_when_llm_not_ready(self) -> None:
        async def _run() -> None:
            status_calls: list[str] = []
            persist_mock = AsyncMock()
            update_eval_mock = AsyncMock()

            patches = self._patch_stack(
                status_calls=status_calls,
                persist_mock=persist_mock,
                update_eval_mock=update_eval_mock,
                llm_ready=False,
            )

            p1_mock = AsyncMock()
            p2_mock = AsyncMock()
            p3_mock = AsyncMock()

            with contextlib.ExitStack() as stack:
                self._enter_all(stack, patches)
                stack.enter_context(
                    patch("app.services.pipeline.run_pass1", new=p1_mock)
                )
                stack.enter_context(
                    patch("app.services.pipeline.run_pass2", new=p2_mock)
                )
                stack.enter_context(
                    patch("app.services.pipeline.run_pass3", new=p3_mock)
                )
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            self.assertEqual(status_calls, ["Testing", "Completed"])
            p1_mock.assert_not_awaited()
            p2_mock.assert_not_awaited()
            p3_mock.assert_not_awaited()
            update_eval_mock.assert_not_awaited()

        asyncio.run(_run())

    def test_evaluation_failed_error_maps_to_evaluation_failed_status(
        self,
    ) -> None:
        from app.services.llm_validator import EvaluationFailedError

        async def _run() -> None:
            status_calls: list[str] = []
            persist_mock = AsyncMock()
            update_eval_mock = AsyncMock()

            pass1_result = {"pass": "pass1", "failures": [], "summary": "ok"}

            patches = self._patch_stack(
                status_calls=status_calls,
                persist_mock=persist_mock,
                update_eval_mock=update_eval_mock,
            )

            p3_mock = AsyncMock()

            with contextlib.ExitStack() as stack:
                self._enter_all(stack, patches)
                stack.enter_context(
                    patch(
                        "app.services.pipeline.run_pass1",
                        new=AsyncMock(return_value=pass1_result),
                    )
                )
                stack.enter_context(
                    patch(
                        "app.services.pipeline.run_pass2",
                        new=AsyncMock(
                            side_effect=EvaluationFailedError(
                                "schema invalid",
                                original_output="bad",
                                validation_errors=["missing field"],
                            )
                        ),
                    )
                )
                stack.enter_context(
                    patch("app.services.pipeline.run_pass3", new=p3_mock)
                )
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            # M2 path completes, then Evaluating, then EVALUATION_FAILED.
            self.assertEqual(
                status_calls,
                ["Testing", "Completed", "Evaluating", "EVALUATION_FAILED"],
            )
            self.assertNotIn("Failed", status_calls)
            p3_mock.assert_not_awaited()
            update_eval_mock.assert_not_awaited()

        asyncio.run(_run())

    def test_needs_human_review_flag_promotes_status_to_awaiting_review(
        self,
    ) -> None:
        async def _run() -> None:
            status_calls: list[str] = []
            persist_mock = AsyncMock()
            update_eval_mock = AsyncMock()

            pass1_result = {"pass": "pass1", "failures": [], "summary": "ok"}
            reasoning = {
                "pass1": pass1_result,
                "pass2": {"skipped": True, "reason": "no_lint_no_rubric"},
            }
            # Low confidence below the default 0.6 threshold should
            # trigger NEEDS_HUMAN_REVIEW via compute_review_flags.
            envelope = self._valid_envelope(confidence=0.30)

            patches = self._patch_stack(
                status_calls=status_calls,
                persist_mock=persist_mock,
                update_eval_mock=update_eval_mock,
            )

            with contextlib.ExitStack() as stack:
                self._enter_all(stack, patches)
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
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            self.assertEqual(
                status_calls,
                ["Testing", "Completed", "Evaluating", "Awaiting Review"],
            )
            persisted_envelope = update_eval_mock.await_args.kwargs[
                "ai_feedback_json"
            ]
            self.assertIn("NEEDS_HUMAN_REVIEW", persisted_envelope["flags"])

        asyncio.run(_run())

    def test_style_guide_version_lifted_into_metadata_from_pass2_findings(
        self,
    ) -> None:
        async def _run() -> None:
            status_calls: list[str] = []
            persist_mock = AsyncMock()
            update_eval_mock = AsyncMock()

            pass1_result = {"pass": "pass1", "failures": [], "summary": "ok"}
            reasoning = {
                "pass1": pass1_result,
                "pass2": {
                    "pass": "pass2",
                    "findings": [
                        {
                            "file_path": "src/main.py",
                            "rule_reference": "PEP8/E501",
                            "severity": "minor",
                            "message": "line too long",
                            "style_guide_source": {
                                "source_title": "PEP 8",
                                "style_guide_version": "2024-05",
                            },
                        }
                    ],
                    "retrieval_status": "ok",
                },
            }
            envelope = self._valid_envelope()

            patches = self._patch_stack(
                status_calls=status_calls,
                persist_mock=persist_mock,
                update_eval_mock=update_eval_mock,
            )

            with contextlib.ExitStack() as stack:
                self._enter_all(stack, patches)
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
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            kwargs = update_eval_mock.await_args.kwargs
            self.assertEqual(
                kwargs["metadata_json"]["style_guide_version"], "2024-05"
            )
            self.assertEqual(
                kwargs["ai_feedback_json"]["metadata"]["style_guide_version"],
                "2024-05",
            )

        asyncio.run(_run())

    def test_unexpected_ai_phase_exception_does_not_clobber_completed_status(
        self,
    ) -> None:
        """A non-EvaluationFailedError raised inside the AI phase falls
        through to the outer ``except Exception`` and marks ``Failed``.

        This pins the contract that schema failures are the *only*
        way to land on ``EVALUATION_FAILED`` — generic bugs still
        surface as ``Failed`` per design-doc terminal-status table.
        """

        async def _run() -> None:
            status_calls: list[str] = []
            persist_mock = AsyncMock()
            update_eval_mock = AsyncMock()

            pass1_result = {"pass": "pass1", "failures": [], "summary": "ok"}

            patches = self._patch_stack(
                status_calls=status_calls,
                persist_mock=persist_mock,
                update_eval_mock=update_eval_mock,
            )

            with contextlib.ExitStack() as stack:
                self._enter_all(stack, patches)
                stack.enter_context(
                    patch(
                        "app.services.pipeline.run_pass1",
                        new=AsyncMock(return_value=pass1_result),
                    )
                )
                stack.enter_context(
                    patch(
                        "app.services.pipeline.run_pass2",
                        new=AsyncMock(side_effect=RuntimeError("boom")),
                    )
                )
                stack.enter_context(
                    patch("app.services.pipeline.logger.exception")
                )
                with tempfile.TemporaryDirectory() as tmp:
                    student = Path(tmp) / "student"
                    student.mkdir()
                    await run_pipeline(
                        MOCK_SUBMISSION_ID,
                        MOCK_ASSIGNMENT_ID,
                        str(student.resolve()),
                        {"title": "r"},
                        "github-pat",
                    )

            self.assertEqual(
                status_calls,
                ["Testing", "Completed", "Evaluating", "Failed"],
            )

        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
