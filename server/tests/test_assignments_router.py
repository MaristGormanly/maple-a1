import json
import uuid
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from app.routers.assignments import (
    AssignmentCreateRequest,
    create_assignment_endpoint,
    get_assignment_endpoint,
)


def _payload(response) -> dict:
    if isinstance(response, dict):
        return response
    return json.loads(response.body)


def _assignment(
    *,
    instructor_id: uuid.UUID,
    title: str = "Test Assignment",
    test_suite_repo_url: str | None = None,
    rubric_id: uuid.UUID | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid.uuid4(),
        title=title,
        instructor_id=instructor_id,
        test_suite_repo_url=test_suite_repo_url,
        rubric_id=rubric_id,
        enable_lint_review=False,
        language_override=None,
    )


class CreateAssignmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_creates_with_test_suite_repo_url(self) -> None:
        instructor_id = uuid.uuid4()
        url = "https://github.com/org/test-suite"
        assignment = _assignment(instructor_id=instructor_id, test_suite_repo_url=url)

        with patch(
            "app.routers.assignments.create_assignment",
            new=AsyncMock(return_value=assignment),
        ):
            response = await create_assignment_endpoint(
                AssignmentCreateRequest(title="Test Assignment", test_suite_repo_url=url),
                db=AsyncMock(),
                current_user={"sub": str(instructor_id)},
            )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["test_suite_repo_url"], url)

    async def test_creates_with_null_test_suite_repo_url(self) -> None:
        instructor_id = uuid.uuid4()
        assignment = _assignment(instructor_id=instructor_id, test_suite_repo_url=None)

        with patch(
            "app.routers.assignments.create_assignment",
            new=AsyncMock(return_value=assignment),
        ):
            response = await create_assignment_endpoint(
                AssignmentCreateRequest(title="Test Assignment"),
                db=AsyncMock(),
                current_user={"sub": str(instructor_id)},
            )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertIsNone(payload["data"]["test_suite_repo_url"])

    async def test_response_is_standard_envelope(self) -> None:
        instructor_id = uuid.uuid4()
        assignment = _assignment(instructor_id=instructor_id)

        with patch(
            "app.routers.assignments.create_assignment",
            new=AsyncMock(return_value=assignment),
        ):
            response = await create_assignment_endpoint(
                AssignmentCreateRequest(title="Test Assignment"),
                db=AsyncMock(),
                current_user={"sub": str(instructor_id)},
            )

        payload = _payload(response)
        for key in ("success", "data", "error", "metadata"):
            self.assertIn(key, payload)

    async def test_invalid_rubric_id_returns_validation_error(self) -> None:
        response = await create_assignment_endpoint(
            AssignmentCreateRequest(title="Test", rubric_id="not-a-uuid"),
            db=AsyncMock(),
            current_user={"sub": str(uuid.uuid4())},
        )

        self.assertEqual(response.status_code, 400)
        payload = _payload(response)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")

    async def test_response_data_contains_all_expected_fields(self) -> None:
        instructor_id = uuid.uuid4()
        assignment = _assignment(instructor_id=instructor_id, test_suite_repo_url="https://github.com/org/suite")

        with patch(
            "app.routers.assignments.create_assignment",
            new=AsyncMock(return_value=assignment),
        ):
            response = await create_assignment_endpoint(
                AssignmentCreateRequest(title="Test Assignment", test_suite_repo_url="https://github.com/org/suite"),
                db=AsyncMock(),
                current_user={"sub": str(instructor_id)},
            )

        data = _payload(response)["data"]
        for field in ("assignment_id", "title", "instructor_id", "test_suite_repo_url",
                      "rubric_id", "enable_lint_review", "language_override"):
            self.assertIn(field, data, msg=f"Missing field: {field}")


class GetAssignmentTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_assignment_including_test_suite_repo_url(self) -> None:
        instructor_id = uuid.uuid4()
        url = "https://github.com/org/test-suite"
        assignment = _assignment(instructor_id=instructor_id, test_suite_repo_url=url)

        with patch(
            "app.routers.assignments.get_assignment_by_id",
            new=AsyncMock(return_value=assignment),
        ):
            response = await get_assignment_endpoint(
                str(assignment.id),
                db=AsyncMock(),
                current_user={"sub": str(instructor_id)},
            )

        payload = _payload(response)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["data"]["test_suite_repo_url"], url)
        self.assertEqual(payload["data"]["assignment_id"], str(assignment.id))

    async def test_non_uuid_path_param_returns_validation_error(self) -> None:
        response = await get_assignment_endpoint(
            "not-a-uuid",
            db=AsyncMock(),
            current_user={"sub": str(uuid.uuid4())},
        )

        self.assertEqual(response.status_code, 400)
        payload = _payload(response)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")

    async def test_unknown_id_returns_not_found(self) -> None:
        with patch(
            "app.routers.assignments.get_assignment_by_id",
            new=AsyncMock(return_value=None),
        ):
            response = await get_assignment_endpoint(
                str(uuid.uuid4()),
                db=AsyncMock(),
                current_user={"sub": str(uuid.uuid4())},
            )

        self.assertEqual(response.status_code, 404)
        payload = _payload(response)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error"]["code"], "NOT_FOUND")
