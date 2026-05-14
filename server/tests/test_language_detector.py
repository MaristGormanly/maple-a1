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

    # ---- Python fallback markers ----

    def test_python_requirements_txt(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "requirements.txt").write_text("pytest>=7\n", encoding="utf-8")
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "python")
        self.assertIsNone(result["version"])
        self.assertEqual(result["source"], "requirements.txt")

    def test_python_setup_py(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "setup.py").write_text("from setuptools import setup\nsetup()\n", encoding="utf-8")
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "python")
        self.assertIsNone(result["version"])
        self.assertEqual(result["source"], "setup.py")

    def test_python_setup_cfg(self) -> None:
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "setup.cfg").write_text("[metadata]\nname = demo\n", encoding="utf-8")
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "python")
        self.assertIsNone(result["version"])
        self.assertEqual(result["source"], "setup.cfg")

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


class TestDetectorPriority(unittest.TestCase):
    """Regression tests for detector ordering — C++/Java must win over Python's *.py glob."""

    def test_cpp_repo_with_python_helper_scripts_detects_cpp(self) -> None:
        # ETLCPP/etl regression: C++ library ships Python build scripts in a
        # subdirectory. The old detector order (python first) returned "python".
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.14)\nproject(etl)\n",
                encoding="utf-8",
            )
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "build.py").write_text("# helper", encoding="utf-8")
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "cpp")
        self.assertEqual(result["source"], "CMakeLists.txt")

    def test_cpp_repo_without_cmake_detects_cpp_via_source_files(self) -> None:
        # Repos that use Makefiles or store CMakeLists.txt in a subdirectory
        # should still be detected as C++ via the *.cpp fallback.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            src = root / "src"
            src.mkdir()
            (src / "main.cpp").write_text("int main() { return 0; }\n", encoding="utf-8")
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "cpp")
        self.assertEqual(result["source"], "*.cpp")

    def test_java_repo_with_python_scripts_detects_java(self) -> None:
        # Maven repo that bundles Python tooling must not be misclassified.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pom.xml").write_text("<project/>", encoding="utf-8")
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "setup.py").write_text("# helper", encoding="utf-8")
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "java")

    def test_pure_python_repo_still_detected_after_reorder(self) -> None:
        # Reordering must not break plain Python repos.
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "requirements.txt").write_text("pytest\n", encoding="utf-8")
            result = detect_language_version(tmp)
        self.assertEqual(result["language"], "python")


if __name__ == "__main__":
    unittest.main()
