import unittest

from pydantic import HttpUrl, TypeAdapter

from app.main import parse_github_repo_url

_url_adapter = TypeAdapter(HttpUrl)


def _parse(raw: str) -> tuple[str, str]:
    return parse_github_repo_url(_url_adapter.validate_python(raw))


class ParseGitHubRepoUrlTests(unittest.TestCase):

    # --- valid: basic owner/repo ---

    def test_basic_https(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo"), ("owner", "repo"))

    def test_www_prefix(self) -> None:
        self.assertEqual(_parse("https://www.github.com/owner/repo"), ("owner", "repo"))

    def test_strips_dot_git_suffix(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo.git"), ("owner", "repo"))

    # --- valid: URLs with path suffixes (the hardening) ---

    def test_tree_branch(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/tree/main"), ("owner", "repo"))

    def test_tree_nested_path(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/tree/main/src/lib"), ("owner", "repo"))

    def test_blob_file(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/blob/main/README.md"), ("owner", "repo"))

    def test_issues(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/issues"), ("owner", "repo"))

    def test_issues_number(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/issues/42"), ("owner", "repo"))

    def test_pull_request(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/pull/7"), ("owner", "repo"))

    def test_actions(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/actions"), ("owner", "repo"))

    def test_settings(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/settings"), ("owner", "repo"))

    def test_commit_sha(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo/commit/abc123"), ("owner", "repo"))

    def test_dot_git_with_suffix(self) -> None:
        self.assertEqual(_parse("https://github.com/owner/repo.git/tree/main"), ("owner", "repo"))

    # --- invalid: rejected URLs ---

    def test_rejects_non_github_host(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _parse("https://gitlab.com/owner/repo")
        self.assertIn("github.com", str(ctx.exception))

    def test_rejects_owner_only(self) -> None:
        with self.assertRaises(ValueError):
            _parse("https://github.com/owner")

    def test_rejects_bare_github(self) -> None:
        with self.assertRaises(ValueError):
            _parse("https://github.com/")

    def test_rejects_empty_owner(self) -> None:
        with self.assertRaises(ValueError):
            _parse("https://github.com//repo")


if __name__ == "__main__":
    unittest.main()
