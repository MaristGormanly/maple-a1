from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.cache import (
    build_repository_cache_key,
    create_repository_cache_entry,
    fingerprint_rubric_content,
    load_repository_cache_entry,
    save_repository_cache_entry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_ROOT = Path(__file__).resolve().parent


class RepositoryCacheTests(unittest.TestCase):
    def test_build_repository_cache_key_uses_commit_hash_and_rubric_digest(self) -> None:
        cache_key = build_repository_cache_key("abc123", "rubric-digest-1")
        same_cache_key = build_repository_cache_key("abc123", "rubric-digest-1")
        different_rubric_key = build_repository_cache_key("abc123", "rubric-digest-2")

        self.assertEqual(cache_key.value, "abc123::rubric-digest-1")
        self.assertEqual(cache_key.path_token, same_cache_key.path_token)
        self.assertNotEqual(cache_key.path_token, different_rubric_key.path_token)

    def test_fingerprint_rubric_content_normalizes_equivalent_json_payloads(self) -> None:
        rubric_one = {
            "criteria": [
                {"name": "Correctness", "description": "  Meets   spec  "},
                {"name": "Style", "description": "Clear naming"},
            ],
            "title": "Assignment 1",
        }
        rubric_two = {
            "title": "Assignment 1",
            "criteria": [
                {"description": "Meets spec", "name": "Correctness"},
                {"description": "Clear naming", "name": "Style"},
            ],
        }

        fingerprint_one = fingerprint_rubric_content(rubric_one)
        fingerprint_two = fingerprint_rubric_content(rubric_two)

        self.assertEqual(fingerprint_one.digest, fingerprint_two.digest)
        self.assertEqual(fingerprint_one.normalization_method, "json_canonicalization")

    def test_fingerprint_rubric_content_normalizes_equivalent_text_payloads(self) -> None:
        fingerprint_one = fingerprint_rubric_content("Criterion A\n\nCriterion B")
        fingerprint_two = fingerprint_rubric_content("  Criterion A Criterion B  ")

        self.assertEqual(fingerprint_one.digest, fingerprint_two.digest)
        self.assertEqual(
            fingerprint_one.normalization_method,
            "text_whitespace_canonicalization",
        )

    def test_load_repository_cache_entry_returns_saved_entry_and_drops_stale_paths(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            temp_root = Path(tmp_dir)
            cache_index_path = temp_root / "repository-cache-index.json"
            repo_path = temp_root / "cached-repo"
            repo_path.mkdir(parents=True, exist_ok=True)

            rubric_fingerprint = fingerprint_rubric_content({"criteria": ["Correctness"]})
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

            loaded_entry = load_repository_cache_entry(cache_index_path, PROJECT_ROOT, cache_key.value)
            self.assertIsNotNone(loaded_entry)
            self.assertEqual(loaded_entry.local_repo_path, str(repo_path.relative_to(PROJECT_ROOT)))

            repo_path.rmdir()
            stale_entry = load_repository_cache_entry(cache_index_path, PROJECT_ROOT, cache_key.value)
            self.assertIsNone(stale_entry)


if __name__ == "__main__":
    unittest.main()
