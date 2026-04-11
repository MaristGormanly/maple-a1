import asyncio
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


def _fake_assignment(suite_url: str | None = "https://github.com/org/tests.git"):
    a = MagicMock()
    a.test_suite_repo_url = suite_url
    a.language_override = None
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


if __name__ == "__main__":
    unittest.main()
