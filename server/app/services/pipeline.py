from __future__ import annotations

import logging
import shutil
import tempfile
import uuid
from pathlib import Path

from ..models.database import async_session_maker
from .assignments import get_assignment_by_id
from .docker_client import run_container
from .language_detector import detect_language_version
from .scoring import calculate_deterministic_score
from .submissions import persist_evaluation_result, update_submission_status
from .test_parser import parse_test_results

logger = logging.getLogger(__name__)

_CONTAINER_TIMEOUT_SECONDS = 30



async def run_pipeline(
    submission_id: uuid.UUID,
    assignment_id: uuid.UUID | None,
    student_repo_path: str,
    rubric_content: object,
    github_pat: str,
) -> None:
    if assignment_id is None:
        return

    test_suite_dir: Path | None = None
    try:
        async with async_session_maker() as db:
            if await update_submission_status(db, submission_id, "Testing") is None:
                logger.warning("run_pipeline: submission %s not found", submission_id)
                return
            assignment = await get_assignment_by_id(db, assignment_id)
            if assignment is None:
                await update_submission_status(db, submission_id, "Failed")
                return
            suite_url = (assignment.test_suite_repo_url or "").strip()
            if not suite_url:
                await update_submission_status(db, submission_id, "Failed")
                return
            language_override = assignment.language_override

        test_suite_dir = Path(tempfile.mkdtemp(prefix="maple-testsuite-"))
        from .. import main as app_main

        await app_main.clone_repository(suite_url, test_suite_dir, github_pat)

        lang = detect_language_version(student_repo_path, language_override)
        language = lang.get("language", "")
        container = await run_container(
            language,
            student_repo_path,
            str(test_suite_dir.resolve()),
            timeout_seconds=_CONTAINER_TIMEOUT_SECONDS,
        )

        parsed = parse_test_results(container.stdout, container.stderr, container.exit_code)
        score = calculate_deterministic_score(parsed, rubric_content)

        metadata_json = {
            "language": lang,
            "exit_code": container.exit_code,
            "resource_constraint_metadata": parsed.get("resource_constraint_metadata"),
            "test_summary": {
                "framework": parsed.get("framework", "unknown"),
                "passed": parsed.get("passed", 0),
                "failed": parsed.get("failed", 0),
                "errors": parsed.get("errors", 0),
                "skipped": parsed.get("skipped", 0),
            },
        }

        async with async_session_maker() as db:
            await persist_evaluation_result(
                db,
                submission_id=submission_id,
                deterministic_score=score,
                metadata_json=metadata_json,
            )
            await update_submission_status(db, submission_id, "Completed")
    except Exception:
        logger.exception("run_pipeline failed for submission %s", submission_id)
        try:
            async with async_session_maker() as db:
                await update_submission_status(db, submission_id, "Failed")
        except Exception:
            logger.exception(
                "run_pipeline: could not mark submission %s Failed", submission_id
            )
    finally:
        if test_suite_dir is not None and test_suite_dir.exists():
            shutil.rmtree(test_suite_dir, ignore_errors=True)
