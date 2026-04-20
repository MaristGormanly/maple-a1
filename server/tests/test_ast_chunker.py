"""Unit tests for ``app.services.ast_chunker``."""

from __future__ import annotations

import unittest
from pathlib import Path

from app.services.ast_chunker import (
    CodeChunk,
    extract_chunks,
    regex_fallback_limitations,
    supported_languages,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "ast_chunker"


def _by_name(chunks: list[CodeChunk]) -> dict[str, CodeChunk]:
    return {c.name: c for c in chunks}


class ChunkerMetadataTests(unittest.TestCase):
    def test_supported_languages(self) -> None:
        self.assertEqual(
            set(supported_languages()),
            {"python", "javascript", "typescript", "java"},
        )

    def test_regex_fallback_limitations_documented(self) -> None:
        limits = regex_fallback_limitations()
        self.assertTrue(len(limits) >= 3)
        self.assertTrue(all(isinstance(line, str) and line for line in limits))


class PythonChunkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = _FIXTURES / "sample.py"
        self.chunks = extract_chunks(self.path, min_tokens=0)

    def test_extracts_top_level_functions_and_classes(self) -> None:
        names = [c.name for c in self.chunks]
        self.assertIn("add", names)
        self.assertIn("fetch_user", names)
        self.assertIn("Calculator", names)
        self.assertIn("_internal_helper", names)

    def test_kinds_are_assigned(self) -> None:
        by_name = _by_name(self.chunks)
        self.assertEqual(by_name["add"].kind, "function")
        self.assertEqual(by_name["fetch_user"].kind, "function")
        self.assertEqual(by_name["Calculator"].kind, "class")

    def test_line_ranges_are_inclusive_and_text_matches(self) -> None:
        by_name = _by_name(self.chunks)
        add_chunk = by_name["add"]
        self.assertGreater(add_chunk.start_line, 0)
        self.assertGreaterEqual(add_chunk.end_line, add_chunk.start_line)
        self.assertIn("def add(a, b):", add_chunk.text)
        self.assertIn("return a + b", add_chunk.text)

    def test_file_path_and_language_are_set(self) -> None:
        for chunk in self.chunks:
            self.assertEqual(chunk.file_path, str(self.path))
            self.assertEqual(chunk.language, "python")

    def test_oversized_class_is_split_into_methods(self) -> None:
        big = extract_chunks(_FIXTURES / "big_class.py", max_tokens=80, min_tokens=0)
        kinds = [c.kind for c in big]
        names = [c.name for c in big]

        self.assertIn("class_header", kinds)
        self.assertIn("method", kinds)
        self.assertIn("BigClass.__init__", names)
        self.assertIn("BigClass.method_one", names)
        self.assertIn("BigClass.method_two", names)
        self.assertIn("BigClass.method_three", names)

    def test_small_class_kept_as_single_chunk(self) -> None:
        chunks = extract_chunks(self.path, max_tokens=10_000, min_tokens=0)
        names_kinds = {c.name: c.kind for c in chunks}
        self.assertEqual(names_kinds.get("Calculator"), "class")

    def test_syntax_error_returns_empty_list(self) -> None:
        result = extract_chunks(
            "broken.py",
            source="def oops(\n    return 1\n",
        )
        self.assertEqual(result, [])

    def test_in_memory_source_overrides_file_read(self) -> None:
        result = extract_chunks(
            "virtual.py",
            source="def only_one():\n    return 1\n",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "only_one")
        self.assertEqual(result[0].kind, "function")


class JavaScriptChunkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunks = extract_chunks(_FIXTURES / "sample.js", min_tokens=0)

    def test_detects_function_arrow_class_and_export(self) -> None:
        names = [c.name for c in self.chunks]
        self.assertIn("topLevelFn", names)
        self.assertIn("arrowFn", names)
        self.assertIn("Greeter", names)
        self.assertIn("exportedFn", names)

    def test_brace_matcher_handles_braces_inside_strings(self) -> None:
        by_name = _by_name(self.chunks)
        exported = by_name["exportedFn"]
        self.assertIn("return 42;", exported.text)
        self.assertTrue(exported.text.rstrip().endswith("}"))

    def test_class_text_contains_full_body(self) -> None:
        by_name = _by_name(self.chunks)
        greeter = by_name["Greeter"]
        self.assertIn("constructor(name)", greeter.text)
        self.assertIn("greet()", greeter.text)
        self.assertTrue(greeter.text.rstrip().endswith("}"))


class TypeScriptChunkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunks = extract_chunks(_FIXTURES / "sample.ts", min_tokens=0)

    def test_detects_function_arrow_and_class(self) -> None:
        names = [c.name for c in self.chunks]
        self.assertIn("makeUser", names)
        self.assertIn("upper", names)
        self.assertIn("UserService", names)

    def test_language_label_is_typescript(self) -> None:
        for c in self.chunks:
            self.assertEqual(c.language, "typescript")


class JavaChunkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunks = extract_chunks(_FIXTURES / "Sample.java", min_tokens=0)

    def test_detects_outer_class_and_methods(self) -> None:
        names = [c.name for c in self.chunks]
        self.assertIn("Sample", names)
        self.assertIn("increment", names)
        self.assertIn("describe", names)

    def test_detects_interface(self) -> None:
        names = [c.name for c in self.chunks]
        self.assertIn("Greeter", names)


class MergeTests(unittest.TestCase):
    def test_small_adjacent_python_functions_are_merged(self) -> None:
        source = (
            "def a():\n    return 1\n\n"
            "def b():\n    return 2\n\n"
            "def c():\n    return 3\n"
        )
        chunks = extract_chunks("merge.py", source=source, min_tokens=10_000)
        self.assertEqual(len(chunks), 1)
        merged = chunks[0]
        self.assertEqual(merged.kind, "merged")
        self.assertEqual(merged.start_line, 1)
        self.assertGreaterEqual(merged.end_line, 8)


class UnknownLanguageTests(unittest.TestCase):
    def test_unknown_extension_returns_empty(self) -> None:
        result = extract_chunks("foo.unknown", source="something()")
        self.assertEqual(result, [])

    def test_explicit_language_override(self) -> None:
        result = extract_chunks(
            "foo.txt",
            source="def f():\n    return 1\n",
            language="python",
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "f")


if __name__ == "__main__":
    unittest.main()
