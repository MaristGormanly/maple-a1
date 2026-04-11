import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock

from app.routers.submissions import get_submission


def _payload(response) -> dict:
    if isinstance(response, dict):
        return response
    return json.loads(response.body)


def _submission(*, student_id: uuid.UUID, instructor_id: uuid.UUID):
    assignment_id = uuid.uuid4()
    return SimpleNamespace(
        id=uuid.uuid4(),
        assignment_id=assignment_id,
        student_id=student_id,
        github_repo_url="https://github.com/example/student-repo",
        commit_hash="abc123",
        status="Pending",
        created_at=datetime.now(timezone.utc),
        evaluation_result=None,
        assignment=SimpleNamespace(
            id=assignment_id,
            instructor_id=instructor_id,
        ),
    )


class GetSubmissionAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _db_with_submission(submission):
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = submission
        db.execute.return_value = result
        return db

    async def test_student_cannot_read_another_students_submission(self) -> None:
        owner_id = uuid.uuid4()
        other_student_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(other_student_id), "role": "Student"},
        )

        self.assertEqual(response.status_code, 403)
        payload = _payload(response)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "FORBIDDEN")
        self.assertEqual(payload["error"]["message"], "Access denied.")

    async def test_submission_owner_can_read_their_submission(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(owner_id), "role": "Student"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["submission_id"], str(submission.id))

    async def test_assignment_instructor_can_read_submission(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(instructor_id), "role": "Instructor"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["student_id"], str(owner_id))

    async def test_admin_can_read_any_submission(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        admin_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(admin_id), "role": "Admin"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])

    async def test_submission_without_evaluation_has_no_evaluation_key(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)
        submission.evaluation_result = None

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(owner_id), "role": "Student"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertNotIn("evaluation", payload["data"])

    async def test_submission_with_evaluation_includes_score_and_null_feedback(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)
        submission.evaluation_result = SimpleNamespace(
            deterministic_score=85.0,
            ai_feedback_json=None,
            metadata_json={
                "language": {"language": "python", "version": "3.12", "source": "pyproject.toml"},
                "test_summary": {"framework": "pytest", "passed": 17, "failed": 3, "errors": 0, "skipped": 0},
            },
        )

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(owner_id), "role": "Student"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertIn("evaluation", payload["data"])
        self.assertEqual(payload["data"]["evaluation"]["deterministic_score"], 85.0)
        self.assertIsNone(payload["data"]["evaluation"]["ai_feedback"])
        self.assertEqual(
            payload["data"]["evaluation"]["metadata"]["language"]["language"],
            "python",
        )
        self.assertEqual(payload["data"]["evaluation"]["metadata"]["test_summary"]["passed"], 17)

    async def test_submission_status_reflects_testing(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)
        submission.status = "Testing"

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(owner_id), "role": "Student"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["status"], "Testing")

    async def test_submission_status_reflects_completed(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)
        submission.status = "Completed"

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(owner_id), "role": "Student"},
        )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["status"], "Completed")

