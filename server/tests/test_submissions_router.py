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


class AiFeedbackRecommendationsSerializationTests(unittest.IsolatedAsyncioTestCase):
    """Pin the contract that plural per-criterion ``recommendations`` are flattened.

    Pass 3's :data:`CRITERIA_SCORE_SCHEMA` emits a plural array; the
    earlier serializer scanned for a singular ``recommendation`` and
    therefore returned an empty list to the frontend even when the LLM
    produced valid recommendation objects.
    """

    @staticmethod
    def _db_with_submission(submission):
        db = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = submission
        db.execute.return_value = result
        return db

    @staticmethod
    def _rec(file_path: str, line_start: int) -> dict:
        return {
            "file_path": file_path,
            "line_range": {"start": line_start, "end": line_start + 1},
            "original_snippet": "x = 1",
            "revised_snippet": "x = 2",
            "diff": "@@ -1,1 +1,1 @@\n-x = 1\n+x = 2\n",
        }

    async def test_plural_recommendations_are_flattened_for_privileged_viewer(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)
        submission.status = "Awaiting Review"

        rec_a = self._rec("src/a.py", 10)
        rec_b = self._rec("src/b.py", 22)
        rec_c = self._rec("src/c.py", 33)

        submission.evaluation_result = SimpleNamespace(
            deterministic_score=80.0,
            review_status="pending",
            instructor_notes=None,
            ai_feedback_json={
                "criteria_scores": [
                    {
                        "name": "Correctness",
                        "score": 80,
                        "level": "Proficient",
                        "justification": "ok",
                        "confidence": 0.9,
                        "recommendations": [rec_a, rec_b],
                    },
                    {
                        "name": "Style",
                        "score": 70,
                        "level": "Developing",
                        "justification": "naming",
                        "confidence": 0.7,
                        "recommendations": [rec_c],
                    },
                ],
                "flags": [],
                "metadata": {"language": "python"},
            },
            metadata_json={
                "language": {"language": "python"},
                "test_summary": {"framework": "pytest", "passed": 1, "failed": 0, "errors": 0, "skipped": 0},
            },
        )

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(instructor_id), "role": "Instructor"},
        )
        payload = _payload(response)
        self.assertTrue(payload["success"])
        recommendations = payload["data"]["evaluation"]["ai_feedback"]["recommendations"]
        self.assertEqual(len(recommendations), 3)
        self.assertEqual(
            [r["file_path"] for r in recommendations],
            ["src/a.py", "src/b.py", "src/c.py"],
        )

    async def test_singular_recommendation_field_is_still_supported(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)
        submission.status = "Completed"

        rec = self._rec("legacy.py", 5)

        submission.evaluation_result = SimpleNamespace(
            deterministic_score=90.0,
            review_status="approved",
            instructor_notes=None,
            ai_feedback_json={
                "criteria_scores": [
                    {
                        "name": "Correctness",
                        "score": 90,
                        "level": "Exemplary",
                        "justification": "ok",
                        "confidence": 0.95,
                        "recommendation": rec,
                    },
                ],
                "flags": [],
                "metadata": {},
            },
            metadata_json=None,
        )

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(owner_id), "role": "Student"},
        )
        payload = _payload(response)
        recommendations = payload["data"]["evaluation"]["ai_feedback"]["recommendations"]
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["file_path"], "legacy.py")

    async def test_ai_feedback_hidden_from_unprivileged_viewer_pre_approval(self) -> None:
        owner_id = uuid.uuid4()
        instructor_id = uuid.uuid4()
        submission = _submission(student_id=owner_id, instructor_id=instructor_id)
        submission.status = "Awaiting Review"
        submission.evaluation_result = SimpleNamespace(
            deterministic_score=80.0,
            review_status="pending",
            instructor_notes=None,
            ai_feedback_json={
                "criteria_scores": [
                    {
                        "name": "Correctness",
                        "score": 80,
                        "level": "Proficient",
                        "justification": "ok",
                        "confidence": 0.9,
                        "recommendations": [self._rec("a.py", 1)],
                    },
                ],
                "flags": [],
                "metadata": {},
            },
            metadata_json=None,
        )

        db = self._db_with_submission(submission)

        response = await get_submission(
            str(submission.id),
            db=db,
            current_user={"sub": str(owner_id), "role": "Student"},
        )
        payload = _payload(response)
        self.assertIsNone(payload["data"]["evaluation"]["ai_feedback"])

