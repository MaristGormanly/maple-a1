import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services.language_detector import detect_language_version


class DetectLanguageVersionTests(unittest.TestCase):
    # ---- Python ----

    def test_python_pyproject_requires_python(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text(
                '[project]\nname = "demo"\nrequires-python = ">=3.11"\n',
                encoding="utf-8",
            )
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "python")
        self.assertEqual(result["version"], ">=3.11")
        self.assertEqual(result["source"], "pyproject.toml")
        self.assertFalse(result["override_applied"])

    def test_python_poetry_dependency(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text(
                '[tool.poetry.dependencies]\npython = "^3.10"\n',
                encoding="utf-8",
            )
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "python")
        self.assertEqual(result["version"], "^3.10")

    # ---- JavaScript ----

    def test_javascript_package_json(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "package.json").write_text(
                '{"name": "app", "engines": {"node": ">=18"}}',
                encoding="utf-8",
            )
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "javascript")
        self.assertEqual(result["version"], ">=18")
        self.assertEqual(result["source"], "package.json")
        self.assertFalse(result["override_applied"])

    # ---- TypeScript ----

    def test_typescript_via_dev_dependency(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "package.json").write_text(
                '{"name": "app", "devDependencies": {"typescript": "^5.0"}, "engines": {"node": ">=20"}}',
                encoding="utf-8",
            )
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "typescript")
        self.assertEqual(result["version"], ">=20")

    # ---- Java ----

    def test_java_pom_xml(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "pom.xml").write_text(
                '<?xml version="1.0"?>\n'
                '<project xmlns="http://maven.apache.org/POM/4.0.0">\n'
                "  <properties>\n"
                "    <java.version>17</java.version>\n"
                "  </properties>\n"
                "</project>\n",
                encoding="utf-8",
            )
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "java")
        self.assertEqual(result["version"], "17")
        self.assertEqual(result["source"], "pom.xml")

    # ---- C++ ----

    def test_cpp_cmakelists(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.14)\n"
                "project(demo)\n"
                "set(CMAKE_CXX_STANDARD 20)\n",
                encoding="utf-8",
            )
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "cpp")
        self.assertEqual(result["version"], "20")
        self.assertEqual(result["source"], "CMakeLists.txt")

    # ---- override ----

    def test_override_takes_precedence(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text(
                '[project]\nname = "x"\nrequires-python = ">=3.12"\n',
                encoding="utf-8",
            )
            result = detect_language_version(tmp, language_override="rust")
        self.assertEqual(result["language"], "rust")
        self.assertIsNone(result["version"])
        self.assertEqual(result["source"], "language_override")
        self.assertTrue(result["override_applied"])

    # ---- empty directory ----

    def test_empty_directory_returns_unknown(self) -> None:
        with TemporaryDirectory() as tmp:
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "unknown")
        self.assertIsNone(result["version"])
        self.assertFalse(result["override_applied"])

    # ---- malformed config ----

    def test_malformed_pyproject_does_not_crash(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "pyproject.toml").write_text(
                "this is not valid toml {{{}}}",
                encoding="utf-8",
            )
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "python")
        self.assertIsNone(result["version"])


if __name__ == "__main__":
    unittest.main()
