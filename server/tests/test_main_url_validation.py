import unittest

from pydantic import HttpUrl, TypeAdapter

from app.main import parse_github_repo_url


class ParseGitHubRepoUrlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.url_adapter = TypeAdapter(HttpUrl)

    def test_accepts_https_github_repository_url(self) -> None:
        parsed = self.url_adapter.validate_python(
            "https://github.com/example-org/example-repo"
        )

        owner, repo = parse_github_repo_url(parsed)

        self.assertEqual(owner, "example-org")
        self.assertEqual(repo, "example-repo")

    def test_rejects_http_github_repository_url(self) -> None:
        parsed = self.url_adapter.validate_python(
            "http://github.com/example-org/example-repo"
        )

        with self.assertRaisesRegex(ValueError, "must use https://"):
            parse_github_repo_url(parsed)


if __name__ == "__main__":
    unittest.main()
