from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.cache import (
    build_repository_cache_key,
    create_repository_cache_entry,
    fingerprint_rubric_content,
    load_repository_cache_entry,
    save_repository_cache_entry,
)
from app.main import GitHubRepoMetadata, MapleAPIError, app
from app.preprocessing import RepositoryPreprocessingError


TEST_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class EvaluateSubmissionIntegrationTests(unittest.TestCase):
    def test_evaluate_submission_rejects_non_github_urls_before_clone_logic_runs(self) -> None:
        with patch("app.main.get_required_github_pat") as pat_mock, patch(
            "app.main.validate_github_repo_access",
            new=AsyncMock(),
        ) as access_mock:
            client = TestClient(app)
            response = client.post(
                "/api/v1/code-eval/evaluate",
                json={
                    "github_url": "https://example.com/student/example-assignment",
                    "assignment_id": "asgn_abc123",
                    "rubric": self._sample_rubric(),
                },
            )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload["success"])
        self.assertIsNone(payload["data"])
        self.assertEqual(payload["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("github.com", payload["error"]["message"])
        pat_mock.assert_not_called()
        access_mock.assert_not_called()

    def test_evaluate_submission_returns_configuration_error_when_github_pat_is_missing(self) -> None:
        with patch(
            "app.main.get_required_github_pat",
            side_effect=RuntimeError(
                "GITHUB_PAT is not configured. Set it in the environment or in .env."
            ),
        ), patch(
            "app.main.validate_github_repo_access",
            new=AsyncMock(),
        ) as access_mock:
            client = TestClient(app)
            response = client.post(
                "/api/v1/code-eval/evaluate",
                json={
                    "github_url": "https://github.com/student/example-assignment",
                    "assignment_id": "asgn_abc123",
                    "rubric": self._sample_rubric(),
                },
            )

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assert_error_response_contract(
            payload=payload,
            expected_code="CONFIGURATION_ERROR",
            expected_message="GITHUB_PAT is not configured. Set it in the environment or in .env.",
        )
        access_mock.assert_not_called()

    def test_evaluate_submission_returns_authentication_error_for_invalid_pat(self) -> None:
        with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
            "app.main.validate_github_repo_access",
            new=AsyncMock(
                side_effect=MapleAPIError(
                    status_code=401,
                    code="AUTHENTICATION_ERROR",
                    message="GITHUB_PAT is invalid or expired.",
                )
            ),
        ), patch(
            "app.main.resolve_repository_head_commit_hash",
            new=AsyncMock(),
        ) as resolve_sha_mock:
            client = TestClient(app)
            response = client.post(
                "/api/v1/code-eval/evaluate",
                json={
                    "github_url": "https://github.com/student/example-assignment",
                    "assignment_id": "asgn_abc123",
                    "rubric": self._sample_rubric(),
                },
            )

        self.assertEqual(response.status_code, 401)
        payload = response.json()
        self.assert_error_response_contract(
            payload=payload,
            expected_code="AUTHENTICATION_ERROR",
            expected_message="GITHUB_PAT is invalid or expired.",
        )
        resolve_sha_mock.assert_not_called()

    def test_evaluate_submission_returns_validation_error_for_inaccessible_repository(self) -> None:
        with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
            "app.main.validate_github_repo_access",
            new=AsyncMock(
                side_effect=MapleAPIError(
                    status_code=400,
                    code="VALIDATION_ERROR",
                    message="Repository not found or inaccessible with the current GITHUB_PAT.",
                )
            ),
        ), patch(
            "app.main.resolve_repository_head_commit_hash",
            new=AsyncMock(),
        ) as resolve_sha_mock, patch(
            "app.main.clone_repository",
            new=AsyncMock(),
        ) as clone_mock:
            client = TestClient(app)
            response = client.post(
                "/api/v1/code-eval/evaluate",
                json={
                    "github_url": "https://github.com/student/example-assignment",
                    "assignment_id": "asgn_abc123",
                    "rubric": self._sample_rubric(),
                },
            )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assert_error_response_contract(
            payload=payload,
            expected_code="VALIDATION_ERROR",
            expected_message="Repository not found or inaccessible with the current GITHUB_PAT.",
        )
        resolve_sha_mock.assert_not_called()
        clone_mock.assert_not_called()

    def test_evaluate_submission_rejects_empty_teacher_rubric(self) -> None:
        with patch("app.main.get_required_github_pat") as pat_mock, patch(
            "app.main.validate_github_repo_access",
            new=AsyncMock(),
        ) as access_mock:
            client = TestClient(app)
            response = client.post(
                "/api/v1/code-eval/evaluate",
                json={
                    "github_url": "https://github.com/student/example-assignment",
                    "assignment_id": "asgn_abc123",
                    "rubric": {},
                },
            )

        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assert_error_response_contract(
            payload=payload,
            expected_code="VALIDATION_ERROR",
            expected_message="Value error, rubric must be a non-empty string, object, or array",
        )
        pat_mock.assert_not_called()
        access_mock.assert_not_called()

    def test_evaluate_submission_clones_preprocesses_and_records_cache_entry_on_cache_miss(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            temp_root = Path(tmp_dir)
            staging_path = temp_root / "staging-repo"
            repo_path = temp_root / "cached-repo"
            cache_index_path = temp_root / "repository-cache-index.json"
            expected_local_path = str(repo_path.relative_to(PROJECT_ROOT))

            def clone_side_effect(_clone_url: str, destination_path: Path, _github_pat: str) -> str:
                self._write_file(destination_path / ".git" / "config", "[core]\nrepositoryformatversion = 0\n")
                self._write_file(
                    destination_path / "node_modules" / "left-pad" / "index.js",
                    "module.exports = {};\n",
                )
                self._write_file(destination_path / "venv" / "bin" / "python", "")
                self._write_file(destination_path / "build" / "native.so", "binary")
                self._write_file(destination_path / "src" / "main.py", "print('hello')\n")
                return "abc123"

            with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
                "app.main.validate_github_repo_access",
                new=AsyncMock(
                    return_value=GitHubRepoMetadata(
                        full_name="student/example-assignment",
                        default_branch="main",
                        visibility="private",
                        clone_url="https://github.com/student/example-assignment.git",
                    )
                ),
            ), patch(
                "app.main.resolve_repository_head_commit_hash",
                new=AsyncMock(return_value="abc123"),
            ), patch("app.main.create_staging_clone_path", return_value=staging_path), patch(
                "app.main.determine_raw_clone_path",
                return_value=repo_path,
            ), patch(
                "app.main.CACHE_INDEX_PATH",
                cache_index_path,
            ), patch(
                "app.main.clone_repository",
                new=AsyncMock(side_effect=clone_side_effect),
            ):
                client = TestClient(app)
                response = client.post(
                    "/api/v1/code-eval/evaluate",
                    json={
                        "github_url": "https://github.com/student/example-assignment",
                        "assignment_id": "asgn_abc123",
                        "rubric": self._sample_rubric(),
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assert_success_response_contract(
                payload=payload,
                expected_status="cloned",
                expected_commit_hash="abc123",
                expected_local_repo_path=expected_local_path,
                expected_assignment_id="asgn_abc123",
                expected_rubric=self._sample_rubric(),
            )
            self.assertEqual(payload["data"]["status"], "cloned")
            self.assertEqual(payload["data"]["commit_hash"], "abc123")
            self.assertEqual(payload["data"]["local_repo_path"], expected_local_path)
            self.assertFalse((repo_path / ".git").exists())
            self.assertFalse((repo_path / "node_modules").exists())
            self.assertFalse((repo_path / "venv").exists())
            self.assertFalse((repo_path / "build" / "native.so").exists())
            self.assertTrue((repo_path / "src" / "main.py").exists())

            rubric_fingerprint = fingerprint_rubric_content(self._sample_rubric())
            cache_key = build_repository_cache_key("abc123", rubric_fingerprint.digest)
            cache_entry = load_repository_cache_entry(cache_index_path, PROJECT_ROOT, cache_key.value)
            self.assertIsNotNone(cache_entry)
            self.assertEqual(cache_entry.local_repo_path, expected_local_path)
            self.assertEqual(
                cache_entry.rubric_normalization_method,
                rubric_fingerprint.normalization_method,
            )

    def test_evaluate_submission_skips_clone_and_preprocessing_on_cache_hit(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            temp_root = Path(tmp_dir)
            repo_path = temp_root / "cached-repo"
            cache_index_path = temp_root / "repository-cache-index.json"
            expected_local_path = str(repo_path.relative_to(PROJECT_ROOT))
            self._write_file(repo_path / "src" / "main.py", "print('cached')\n")

            rubric_fingerprint = fingerprint_rubric_content(self._sample_rubric())
            cache_key = build_repository_cache_key("abc123", rubric_fingerprint.digest)
            cache_entry = create_repository_cache_entry(
                cache_key=cache_key,
                assignment_id="asgn_abc123",
                rubric_fingerprint=rubric_fingerprint,
                full_repo_name="student/example-assignment",
                local_repo_path=repo_path,
                project_root=PROJECT_ROOT,
            )
            save_repository_cache_entry(cache_index_path, cache_entry)

            with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
                "app.main.validate_github_repo_access",
                new=AsyncMock(
                    return_value=GitHubRepoMetadata(
                        full_name="student/example-assignment",
                        default_branch="main",
                        visibility="private",
                        clone_url="https://github.com/student/example-assignment.git",
                    )
                ),
            ), patch(
                "app.main.resolve_repository_head_commit_hash",
                new=AsyncMock(return_value="abc123"),
            ), patch(
                "app.main.CACHE_INDEX_PATH",
                cache_index_path,
            ), patch(
                "app.main.clone_repository",
                new=AsyncMock(),
            ) as clone_mock, patch(
                "app.main.preprocess_repository",
            ) as preprocess_mock:
                client = TestClient(app)
                response = client.post(
                    "/api/v1/code-eval/evaluate",
                    json={
                        "github_url": "https://github.com/student/example-assignment",
                        "assignment_id": "asgn_abc123",
                        "rubric": self._sample_rubric(),
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assert_success_response_contract(
                payload=payload,
                expected_status="cached",
                expected_commit_hash="abc123",
                expected_local_repo_path=expected_local_path,
                expected_assignment_id="asgn_abc123",
                expected_rubric=self._sample_rubric(),
            )
            clone_mock.assert_not_called()
            preprocess_mock.assert_not_called()

    def test_evaluate_submission_reclones_when_commit_sha_changes(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            temp_root = Path(tmp_dir)
            stale_repo_path = temp_root / "cached-repo-old"
            refreshed_repo_path = temp_root / "cached-repo-new"
            staging_path = temp_root / "staging-repo"
            cache_index_path = temp_root / "repository-cache-index.json"
            self._write_file(stale_repo_path / "src" / "main.py", "print('cached')\n")

            rubric_fingerprint = fingerprint_rubric_content(self._sample_rubric())
            stale_cache_key = build_repository_cache_key("abc123", rubric_fingerprint.digest)
            stale_cache_entry = create_repository_cache_entry(
                cache_key=stale_cache_key,
                assignment_id="asgn_abc123",
                rubric_fingerprint=rubric_fingerprint,
                full_repo_name="student/example-assignment",
                local_repo_path=stale_repo_path,
                project_root=PROJECT_ROOT,
            )
            save_repository_cache_entry(cache_index_path, stale_cache_entry)

            def clone_side_effect(_clone_url: str, destination_path: Path, _github_pat: str) -> str:
                self._write_file(destination_path / "src" / "main.py", "print('fresh')\n")
                return "def456"

            with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
                "app.main.validate_github_repo_access",
                new=AsyncMock(
                    return_value=GitHubRepoMetadata(
                        full_name="student/example-assignment",
                        default_branch="main",
                        visibility="private",
                        clone_url="https://github.com/student/example-assignment.git",
                    )
                ),
            ), patch(
                "app.main.resolve_repository_head_commit_hash",
                new=AsyncMock(return_value="def456"),
            ), patch("app.main.create_staging_clone_path", return_value=staging_path), patch(
                "app.main.determine_raw_clone_path",
                return_value=refreshed_repo_path,
            ), patch(
                "app.main.CACHE_INDEX_PATH",
                cache_index_path,
            ), patch(
                "app.main.clone_repository",
                new=AsyncMock(side_effect=clone_side_effect),
            ) as clone_mock:
                client = TestClient(app)
                response = client.post(
                    "/api/v1/code-eval/evaluate",
                    json={
                        "github_url": "https://github.com/student/example-assignment",
                        "assignment_id": "asgn_abc123",
                        "rubric": self._sample_rubric(),
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assert_success_response_contract(
                payload=payload,
                expected_status="cloned",
                expected_commit_hash="def456",
                expected_local_repo_path=str(refreshed_repo_path.relative_to(PROJECT_ROOT)),
                expected_assignment_id="asgn_abc123",
                expected_rubric=self._sample_rubric(),
            )
            clone_mock.assert_awaited_once()
            refreshed_cache_key = build_repository_cache_key("def456", rubric_fingerprint.digest)
            refreshed_entry = load_repository_cache_entry(
                cache_index_path,
                PROJECT_ROOT,
                refreshed_cache_key.value,
            )
            self.assertIsNotNone(refreshed_entry)
            self.assertEqual(
                refreshed_entry.local_repo_path,
                str(refreshed_repo_path.relative_to(PROJECT_ROOT)),
            )

    def test_evaluate_submission_reclones_when_teacher_rubric_changes(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            temp_root = Path(tmp_dir)
            stale_repo_path = temp_root / "cached-repo-old"
            refreshed_repo_path = temp_root / "cached-repo-new"
            staging_path = temp_root / "staging-repo"
            cache_index_path = temp_root / "repository-cache-index.json"
            self._write_file(stale_repo_path / "src" / "main.py", "print('cached')\n")

            stale_rubric = {
                "criteria": [
                    {"name": "Correctness", "description": "Award points for passing tests"},
                ]
            }
            refreshed_rubric = {
                "criteria": [
                    {"name": "Correctness", "description": "Award points for passing all tests"},
                ]
            }
            stale_fingerprint = fingerprint_rubric_content(stale_rubric)
            refreshed_fingerprint = fingerprint_rubric_content(refreshed_rubric)
            stale_cache_key = build_repository_cache_key("abc123", stale_fingerprint.digest)
            stale_cache_entry = create_repository_cache_entry(
                cache_key=stale_cache_key,
                assignment_id="asgn_coursework",
                rubric_fingerprint=stale_fingerprint,
                full_repo_name="student/example-assignment",
                local_repo_path=stale_repo_path,
                project_root=PROJECT_ROOT,
            )
            save_repository_cache_entry(cache_index_path, stale_cache_entry)

            def clone_side_effect(_clone_url: str, destination_path: Path, _github_pat: str) -> str:
                self._write_file(destination_path / "src" / "main.py", "print('fresh')\n")
                return "abc123"

            with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
                "app.main.validate_github_repo_access",
                new=AsyncMock(
                    return_value=GitHubRepoMetadata(
                        full_name="student/example-assignment",
                        default_branch="main",
                        visibility="private",
                        clone_url="https://github.com/student/example-assignment.git",
                    )
                ),
            ), patch(
                "app.main.resolve_repository_head_commit_hash",
                new=AsyncMock(return_value="abc123"),
            ), patch("app.main.create_staging_clone_path", return_value=staging_path), patch(
                "app.main.determine_raw_clone_path",
                return_value=refreshed_repo_path,
            ), patch(
                "app.main.CACHE_INDEX_PATH",
                cache_index_path,
            ), patch(
                "app.main.clone_repository",
                new=AsyncMock(side_effect=clone_side_effect),
            ) as clone_mock:
                client = TestClient(app)
                response = client.post(
                    "/api/v1/code-eval/evaluate",
                    json={
                        "github_url": "https://github.com/student/example-assignment",
                        "assignment_id": "asgn_coursework",
                        "rubric": refreshed_rubric,
                    },
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assert_success_response_contract(
                payload=payload,
                expected_status="cloned",
                expected_commit_hash="abc123",
                expected_local_repo_path=str(refreshed_repo_path.relative_to(PROJECT_ROOT)),
                expected_assignment_id="asgn_coursework",
                expected_rubric=refreshed_rubric,
            )
            clone_mock.assert_awaited_once()
            refreshed_cache_key = build_repository_cache_key(
                "abc123",
                refreshed_fingerprint.digest,
            )
            refreshed_entry = load_repository_cache_entry(
                cache_index_path,
                PROJECT_ROOT,
                refreshed_cache_key.value,
            )
            self.assertIsNotNone(refreshed_entry)
            self.assertEqual(refreshed_entry.assignment_id, "asgn_coursework")

    def test_evaluate_submission_returns_cache_error_for_unreadable_cache_metadata(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            temp_root = Path(tmp_dir)
            cache_index_path = temp_root / "repository-cache-index.json"
            cache_index_path.write_text("{not-valid-json", encoding="utf-8")

            with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
                "app.main.validate_github_repo_access",
                new=AsyncMock(
                    return_value=GitHubRepoMetadata(
                        full_name="student/example-assignment",
                        default_branch="main",
                        visibility="private",
                        clone_url="https://github.com/student/example-assignment.git",
                    )
                ),
            ), patch(
                "app.main.resolve_repository_head_commit_hash",
                new=AsyncMock(return_value="abc123"),
            ), patch(
                "app.main.CACHE_INDEX_PATH",
                cache_index_path,
            ), patch(
                "app.main.clone_repository",
                new=AsyncMock(),
            ) as clone_mock, patch(
                "app.main.preprocess_repository",
            ) as preprocess_mock:
                client = TestClient(app)
                response = client.post(
                    "/api/v1/code-eval/evaluate",
                    json={
                        "github_url": "https://github.com/student/example-assignment",
                        "assignment_id": "asgn_abc123",
                        "rubric": self._sample_rubric(),
                    },
                )

            self.assertEqual(response.status_code, 500)
            payload = response.json()
            self.assert_error_response_contract(
                payload=payload,
                expected_code="CACHE_ERROR",
                expected_message="Repository cache index could not be read.",
            )
            clone_mock.assert_not_called()
            preprocess_mock.assert_not_called()

    def test_evaluate_submission_returns_preprocessing_error_when_cleanup_fails(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            temp_root = Path(tmp_dir)
            staging_path = temp_root / "staging-repo"
            repo_path = temp_root / "cached-repo"
            cache_index_path = temp_root / "repository-cache-index.json"

            def clone_side_effect(_clone_url: str, destination_path: Path, _github_pat: str) -> str:
                self._write_file(destination_path / "src" / "main.py", "print('hello')\n")
                return "abc123"

            with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
                "app.main.validate_github_repo_access",
                new=AsyncMock(
                    return_value=GitHubRepoMetadata(
                        full_name="student/example-assignment",
                        default_branch="main",
                        visibility="private",
                        clone_url="https://github.com/student/example-assignment.git",
                    )
                ),
            ), patch(
                "app.main.resolve_repository_head_commit_hash",
                new=AsyncMock(return_value="abc123"),
            ), patch("app.main.create_staging_clone_path", return_value=staging_path), patch(
                "app.main.determine_raw_clone_path", return_value=repo_path
            ), patch("app.main.CACHE_INDEX_PATH", cache_index_path), patch(
                "app.main.clone_repository",
                new=AsyncMock(side_effect=clone_side_effect),
            ), patch(
                "app.main.preprocess_repository",
                side_effect=RepositoryPreprocessingError("preprocessing failed"),
            ):
                client = TestClient(app)
                response = client.post(
                    "/api/v1/code-eval/evaluate",
                    json={
                        "github_url": "https://github.com/student/example-assignment",
                        "assignment_id": "asgn_abc123",
                        "rubric": self._sample_rubric(),
                    },
                )

            self.assertEqual(response.status_code, 500)
            payload = response.json()
            self.assert_error_response_contract(
                payload=payload,
                expected_code="PREPROCESSING_ERROR",
                expected_message="preprocessing failed",
            )

    def test_evaluate_submission_returns_clone_error_when_clone_fails(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            temp_root = Path(tmp_dir)
            staging_path = temp_root / "staging-repo"
            cache_index_path = temp_root / "repository-cache-index.json"

            with patch("app.main.get_required_github_pat", return_value="test-pat"), patch(
                "app.main.validate_github_repo_access",
                new=AsyncMock(
                    return_value=GitHubRepoMetadata(
                        full_name="student/example-assignment",
                        default_branch="main",
                        visibility="private",
                        clone_url="https://github.com/student/example-assignment.git",
                    )
                ),
            ), patch(
                "app.main.resolve_repository_head_commit_hash",
                new=AsyncMock(return_value="abc123"),
            ), patch("app.main.create_staging_clone_path", return_value=staging_path), patch(
                "app.main.CACHE_INDEX_PATH",
                cache_index_path,
            ), patch(
                "app.main.clone_repository",
                new=AsyncMock(
                    side_effect=MapleAPIError(
                        status_code=502,
                        code="CLONE_ERROR",
                        message="Repository clone failed.",
                    )
                ),
            ), patch(
                "app.main.preprocess_repository",
            ) as preprocess_mock:
                client = TestClient(app)
                response = client.post(
                    "/api/v1/code-eval/evaluate",
                    json={
                        "github_url": "https://github.com/student/example-assignment",
                        "assignment_id": "asgn_abc123",
                        "rubric": self._sample_rubric(),
                    },
                )

        self.assertEqual(response.status_code, 502)
        payload = response.json()
        self.assert_error_response_contract(
            payload=payload,
            expected_code="CLONE_ERROR",
            expected_message="Repository clone failed.",
        )
        preprocess_mock.assert_not_called()

    def assert_success_response_contract(
        self,
        *,
        payload: dict,
        expected_status: str,
        expected_commit_hash: str,
        expected_local_repo_path: str,
        expected_assignment_id: str | None,
        expected_rubric: dict[str, object] | list[object] | str,
    ) -> None:
        expected_rubric_digest = fingerprint_rubric_content(expected_rubric).digest
        self.assertTrue(payload["success"])
        self.assertIsNone(payload["error"])
        self.assertIn("data", payload)
        self.assertIn("metadata", payload)
        self.assertTrue(payload["data"]["submission_id"].startswith("sub_"))
        self.assertEqual(payload["data"]["github_url"], "https://github.com/student/example-assignment")
        self.assertEqual(payload["data"]["assignment_id"], expected_assignment_id)
        self.assertEqual(payload["data"]["rubric_digest"], expected_rubric_digest)
        self.assertEqual(payload["data"]["status"], expected_status)
        self.assertEqual(payload["data"]["commit_hash"], expected_commit_hash)
        self.assertEqual(payload["data"]["local_repo_path"], expected_local_repo_path)
        self.assertIn("timestamp", payload["metadata"])
        self.assertEqual(payload["metadata"]["module"], "a1")
        self.assertEqual(payload["metadata"]["version"], "1.0.0")

    def assert_error_response_contract(
        self,
        *,
        payload: dict,
        expected_code: str,
        expected_message: str,
    ) -> None:
        self.assertFalse(payload["success"])
        self.assertIsNone(payload["data"])
        self.assertIn("error", payload)
        self.assertIn("metadata", payload)
        self.assertEqual(payload["error"]["code"], expected_code)
        self.assertEqual(payload["error"]["message"], expected_message)
        self.assertIn("timestamp", payload["metadata"])
        self.assertEqual(payload["metadata"]["module"], "a1")
        self.assertEqual(payload["metadata"]["version"], "1.0.0")

    def _write_file(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def _sample_rubric(self) -> dict[str, object]:
        return {
            "title": "Assignment 1 Review",
            "criteria": [
                {"name": "Correctness", "description": "Program behavior matches the specification"},
                {"name": "Style", "description": "Code is readable and well organized"},
            ],
        }


if __name__ == "__main__":
    unittest.main()
