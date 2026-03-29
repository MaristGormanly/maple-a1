from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.preprocessing import RepositoryPreprocessingError, preprocess_repository


TEST_ROOT = Path(__file__).resolve().parent


class PreprocessRepositoryTests(unittest.TestCase):
    def test_preprocess_repository_strips_targeted_paths_and_keeps_source_files(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            repo_path = Path(tmp_dir) / "repo"
            self._create_fixture_repo(repo_path)

            summary = preprocess_repository(repo_path)

            self.assertEqual(
                summary.removed_directories,
                (
                    ".git",
                    ".venv",
                    "nested/__pycache__",
                    "nested/deeper/node_modules",
                    "nested/venv",
                    "node_modules",
                    "venv",
                ),
            )
            self.assertEqual(
                summary.removed_files,
                (
                    "build/archive.jar",
                    "build/native.so",
                    "build/windows.dll",
                    "compiled/Main.class",
                    "compiled/module.pyc",
                ),
            )
            self.assertFalse((repo_path / ".git").exists())
            self.assertFalse((repo_path / "node_modules").exists())
            self.assertFalse((repo_path / "venv").exists())
            self.assertFalse((repo_path / ".venv").exists())
            self.assertFalse((repo_path / "nested" / "__pycache__").exists())
            self.assertFalse((repo_path / "nested" / "venv").exists())
            self.assertFalse((repo_path / "nested" / "deeper" / "node_modules").exists())
            self.assertFalse((repo_path / "build" / "native.so").exists())
            self.assertFalse((repo_path / "build" / "archive.jar").exists())
            self.assertFalse((repo_path / "build" / "windows.dll").exists())
            self.assertFalse((repo_path / "compiled" / "Main.class").exists())
            self.assertFalse((repo_path / "compiled" / "module.pyc").exists())
            self.assertTrue((repo_path / "src" / "main.py").exists())
            self.assertTrue((repo_path / "nested" / "app.js").exists())
            self.assertTrue((repo_path / "nested" / "deeper" / "keep.ts").exists())
            self.assertTrue((repo_path / "README.md").exists())

    def test_preprocess_repository_removes_nested_targets_without_touching_other_directories(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            repo_path = Path(tmp_dir) / "repo"
            self._write_file(repo_path / "src" / "pkg" / "__pycache__" / "module.pyc", "compiled")
            self._write_file(repo_path / "src" / "pkg" / "module.py", "print('still here')\n")
            self._write_file(repo_path / "web" / "node_modules" / "pkg" / "index.js", "module.exports = {};\n")
            self._write_file(repo_path / "web" / "src" / "index.ts", "export const ready = true;\n")

            summary = preprocess_repository(repo_path)

            self.assertEqual(
                summary.removed_directories,
                ("src/pkg/__pycache__", "web/node_modules"),
            )
            self.assertEqual(summary.removed_files, tuple())
            self.assertTrue((repo_path / "src" / "pkg" / "module.py").exists())
            self.assertTrue((repo_path / "web" / "src" / "index.ts").exists())

    def test_preprocess_repository_keeps_non_targeted_files(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            repo_path = Path(tmp_dir) / "repo"
            self._write_file(repo_path / "package.json", '{ "name": "repo" }\n')
            self._write_file(repo_path / "src" / "main.cpp", "int main() { return 0; }\n")
            self._write_file(repo_path / "docs" / "report.software.md", "# Notes\n")

            summary = preprocess_repository(repo_path)

            self.assertEqual(summary.removed_directories, tuple())
            self.assertEqual(summary.removed_files, tuple())
            self.assertTrue((repo_path / "package.json").exists())
            self.assertTrue((repo_path / "src" / "main.cpp").exists())
            self.assertTrue((repo_path / "docs" / "report.software.md").exists())

    def test_preprocess_repository_rejects_invalid_repo_path(self) -> None:
        with TemporaryDirectory(dir=TEST_ROOT) as tmp_dir:
            invalid_repo_path = Path(tmp_dir) / "missing"

            with self.assertRaises(RepositoryPreprocessingError):
                preprocess_repository(invalid_repo_path)

    def _create_fixture_repo(self, repo_path: Path) -> None:
        self._write_file(repo_path / ".git" / "config", "[core]\nrepositoryformatversion = 0\n")
        self._write_file(repo_path / "node_modules" / "left-pad" / "index.js", "module.exports = {};\n")
        self._write_file(repo_path / "venv" / "bin" / "python", "")
        self._write_file(repo_path / ".venv" / "bin" / "activate", "")
        self._write_file(repo_path / "nested" / "__pycache__" / "module.cpython-313.pyc", "compiled")
        self._write_file(repo_path / "nested" / "venv" / "bin" / "python", "")
        self._write_file(repo_path / "nested" / "deeper" / "node_modules" / "pkg" / "index.js", "module.exports = {};\n")
        self._write_file(repo_path / "build" / "native.so", "binary")
        self._write_file(repo_path / "build" / "archive.jar", "binary")
        self._write_file(repo_path / "build" / "windows.dll", "binary")
        self._write_file(repo_path / "compiled" / "Main.class", "binary")
        self._write_file(repo_path / "compiled" / "module.pyc", "binary")
        self._write_file(repo_path / "src" / "main.py", "print('hello')\n")
        self._write_file(repo_path / "nested" / "app.js", "console.log('ok');\n")
        self._write_file(repo_path / "nested" / "deeper" / "keep.ts", "export const keep = true;\n")
        self._write_file(repo_path / "README.md", "# Sample\n")

    def _write_file(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
