"""AST-aware code chunking for the Pass 2 style review.

Per ``docs/design-doc.md`` §3 §II ("Ingestion Processing & Context
Optimization"):

    The Context Optimizer utilizes an AST parser to implement an
    AST-Aware Chunking strategy. Unlike fixed-size splitting, this
    strategy extracts terminal nodes (functions, classes, or methods)
    as discrete logical units. If a node exceeds the token limit, it
    is recursively split into internal branches; if multiple nodes
    are undersized, they are merged to maintain density.

This module supports:

* **Python** — true AST parsing via the ``ast`` stdlib.  Top-level
  functions, async functions, and classes are each one chunk; class
  bodies are decomposed into per-method chunks when the class
  exceeds the token budget.

* **JavaScript / TypeScript / Java** — a *conservative regex
  fallback*.  No external parser is bundled, so we deliberately avoid
  any pretense of full grammar support.  See ``_REGEX_LIMITATIONS``
  below for an explicit list of cases the regex pass cannot capture.

If the design upgrades to bundled tree-sitter / javalang grammars
later, only the per-language extractor functions need to change —
``extract_chunks``, the ``CodeChunk`` shape, and the merge / split
helpers stay the same.
"""

from __future__ import annotations

import ast
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodeChunk:
    """A logical chunk of source code suitable for a single LLM message.

    ``start_line`` / ``end_line`` are 1-based and inclusive, matching
    AST line numbers and the convention used by ``llm_schemas`` and
    the M2 test parser.
    """

    file_path: str
    language: str
    kind: str
    name: str
    start_line: int
    end_line: int
    text: str
    children: tuple[str, ...] = field(default_factory=tuple)

    @property
    def estimated_tokens(self) -> int:
        return _estimate_tokens(self.text)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Practical token budget per chunk for downstream LLM calls.  4 chars/token
# is the well-known rule-of-thumb for English text and most code.
DEFAULT_MAX_TOKENS: int = 800
DEFAULT_MIN_TOKENS: int = 40

_LANG_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
}

_REGEX_LIMITATIONS: tuple[str, ...] = (
    "Nested functions or methods inside another function are not split out.",
    "Decorators / annotations on multiple lines may not be included in the chunk.",
    "Multi-line string literals containing 'function' / 'class' keywords may produce false positives.",
    "Arrow-function expressions assigned to const/let/var are detected; "
    "anonymous IIFEs and object-literal methods are not.",
    "Generic type parameters (Java/TypeScript) are best-effort matched.",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_chunks(
    file_path: str | Path,
    source: str | None = None,
    *,
    language: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    min_tokens: int = DEFAULT_MIN_TOKENS,
) -> list[CodeChunk]:
    """Extract logical code chunks from a source file.

    Args:
        file_path: Path used for reading (when ``source`` is ``None``)
            and for the ``CodeChunk.file_path`` field.
        source: Optional in-memory source string.  When omitted the
            file is read from disk with UTF-8 decoding.
        language: Override the language inferred from the file
            extension (one of: ``python``, ``javascript``,
            ``typescript``, ``java``).
        max_tokens: Maximum token budget per chunk before recursive
            splitting kicks in.
        min_tokens: Minimum token budget; adjacent chunks below this
            threshold are merged when contiguous.

    Returns:
        A list of :class:`CodeChunk` objects in source order.
    """
    path = Path(file_path)
    text = source if source is not None else path.read_text(encoding="utf-8", errors="replace")

    detected = language or _detect_language(path)
    if detected is None:
        logger.warning("ast_chunker: no language detected for %s — returning empty list", path)
        return []

    if detected == "python":
        raw = _extract_python(str(path), text, max_tokens=max_tokens)
    elif detected in {"javascript", "typescript"}:
        raw = _extract_brace_language(str(path), text, language=detected)
    elif detected == "java":
        raw = _extract_brace_language(str(path), text, language="java")
    else:
        logger.warning("ast_chunker: unsupported language %s for %s", detected, path)
        return []

    return _merge_small_adjacent(raw, min_tokens=min_tokens)


def supported_languages() -> tuple[str, ...]:
    return ("python", "javascript", "typescript", "java")


def regex_fallback_limitations() -> tuple[str, ...]:
    """Documented limitations of the regex fallback (JS/TS/Java).

    Exposed so callers can surface them in NEEDS_HUMAN_REVIEW
    metadata when Pass 2 falls back from a real parser.
    """
    return _REGEX_LIMITATIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_language(path: Path) -> str | None:
    return _LANG_BY_EXT.get(path.suffix.lower())


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token).  Cheap, no external deps."""
    if not text:
        return 0
    return max(1, len(text) // 4)


def _slice_lines(lines: Sequence[str], start: int, end: int) -> str:
    """1-based inclusive line slice."""
    return "\n".join(lines[start - 1 : end])


# ---------------------------------------------------------------------------
# Python — true AST parsing
# ---------------------------------------------------------------------------


def _extract_python(
    file_path: str, source: str, *, max_tokens: int
) -> list[CodeChunk]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        logger.warning(
            "ast_chunker: SyntaxError parsing %s (%s) — returning empty list",
            file_path,
            exc.msg,
        )
        return []

    lines = source.splitlines()
    chunks: list[CodeChunk] = []

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunks.append(_python_chunk(file_path, lines, node, kind="function"))
        elif isinstance(node, ast.ClassDef):
            chunks.extend(
                _python_class_chunks(file_path, lines, node, max_tokens=max_tokens)
            )

    return chunks


def _python_chunk(
    file_path: str,
    lines: Sequence[str],
    node: ast.AST,
    *,
    kind: str,
    name_override: str | None = None,
) -> CodeChunk:
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start) or start
    text = _slice_lines(lines, start, end)
    name = name_override or getattr(node, "name", "<anonymous>")
    return CodeChunk(
        file_path=file_path,
        language="python",
        kind=kind,
        name=name,
        start_line=start,
        end_line=end,
        text=text,
    )


def _python_class_chunks(
    file_path: str,
    lines: Sequence[str],
    cls: ast.ClassDef,
    *,
    max_tokens: int,
) -> list[CodeChunk]:
    """Emit a class chunk; if oversized, split into per-method chunks."""
    whole = _python_chunk(file_path, lines, cls, kind="class")

    if whole.estimated_tokens <= max_tokens:
        return [whole]

    method_chunks: list[CodeChunk] = []
    method_names: list[str] = []
    for child in cls.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            chunk = _python_chunk(
                file_path,
                lines,
                child,
                kind="method",
                name_override=f"{cls.name}.{child.name}",
            )
            method_chunks.append(chunk)
            method_names.append(child.name)

    if not method_chunks:
        return [whole]

    header = CodeChunk(
        file_path=file_path,
        language="python",
        kind="class_header",
        name=cls.name,
        start_line=whole.start_line,
        end_line=method_chunks[0].start_line - 1
        if method_chunks[0].start_line > whole.start_line
        else whole.start_line,
        text=_slice_lines(
            lines,
            whole.start_line,
            max(whole.start_line, method_chunks[0].start_line - 1),
        ),
        children=tuple(method_names),
    )
    return [header, *method_chunks]


# ---------------------------------------------------------------------------
# JavaScript / TypeScript / Java — conservative regex fallback
# ---------------------------------------------------------------------------

# JS/TS: ``function name (...)`` declarations.
_JS_FUNCTION_DECL = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?:export\s+)?(?:async\s+)?function\s+(?P<name>[A-Za-z_$][\w$]*)\s*\(",
    re.MULTILINE,
)

# JS/TS: ``const name = (...) =>`` / ``const name = function`` / ``const name = async (...) =>``
_JS_ARROW_DECL = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?:export\s+)?(?:const|let|var)\s+(?P<name>[A-Za-z_$][\w$]*)\s*"
    r"(?::\s*[^=]+)?\s*=\s*"
    r"(?:async\s+)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)"
    r"(?:\s*:\s*[^={]+?)?"
    r"\s*=>\s*\{",
    re.MULTILINE,
)

# JS/TS: ``class Name { ... }``
_JS_CLASS_DECL = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?:export\s+)?(?:abstract\s+)?class\s+(?P<name>[A-Za-z_$][\w$]*)"
    r"(?:\s*<[^{>]*>)?(?:\s+extends\s+[^\s{]+)?(?:\s+implements\s+[^\{]+)?"
    r"\s*\{",
    re.MULTILINE,
)

# Java: top-level types — class / interface / enum / record.
_JAVA_TYPE_DECL = re.compile(
    r"^(?P<indent>[ \t]*)"
    r"(?:public|private|protected|abstract|final|static|sealed|non-sealed|strictfp|\s)*"
    r"(?:class|interface|enum|record)\s+(?P<name>[A-Za-z_$][\w$]*)"
    r"(?:\s*<[^{>]*>)?[^{]*\{",
    re.MULTILINE,
)

# Java: methods (rough — modifiers, optional generics, return type, name, params).
_JAVA_METHOD_DECL = re.compile(
    r"^(?P<indent>[ \t]+)"
    r"(?:(?:public|private|protected|static|final|abstract|synchronized|native|default|\s)+)?"
    r"(?:<[^>]+>\s+)?"
    r"[\w<>\[\],?\s.]+?\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)\s*\([^;{]*\)\s*"
    r"(?:throws\s+[\w.,\s]+)?\s*\{",
    re.MULTILINE,
)


def _extract_brace_language(
    file_path: str, source: str, *, language: str
) -> list[CodeChunk]:
    lines = source.splitlines()
    chunks: list[CodeChunk] = []

    if language in {"javascript", "typescript"}:
        patterns = [
            (_JS_FUNCTION_DECL, "function"),
            (_JS_ARROW_DECL, "function"),
            (_JS_CLASS_DECL, "class"),
        ]
    else:  # java
        patterns = [
            (_JAVA_TYPE_DECL, "class"),
            (_JAVA_METHOD_DECL, "method"),
        ]

    seen_starts: set[int] = set()
    for pattern, kind in patterns:
        for match in pattern.finditer(source):
            start_line = source[: match.start()].count("\n") + 1
            if start_line in seen_starts:
                continue
            end_line = _find_brace_block_end(source, match.end() - 1)
            if end_line is None:
                continue
            seen_starts.add(start_line)
            text = _slice_lines(lines, start_line, end_line)
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    language=language,
                    kind=kind,
                    name=match.group("name"),
                    start_line=start_line,
                    end_line=end_line,
                    text=text,
                )
            )

    chunks.sort(key=lambda c: c.start_line)
    return chunks


def _find_brace_block_end(source: str, opening_brace_index: int) -> int | None:
    """Return the 1-based line number of the matching closing brace.

    Uses a simple depth counter that ignores braces inside ``//`` line
    comments, ``/* ... */`` block comments, and ``" ... "`` /
    ``' ... '`` string literals.  This is sufficient for typical
    student code; pathological inputs may still confuse it (see
    ``_REGEX_LIMITATIONS``).
    """
    depth = 0
    i = opening_brace_index
    n = len(source)
    in_line_comment = False
    in_block_comment = False
    in_string: str | None = None  # the active quote char, or None

    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
        elif in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 1
        elif in_string is not None:
            if ch == "\\":
                i += 1
            elif ch == in_string:
                in_string = None
        else:
            if ch == "/" and nxt == "/":
                in_line_comment = True
                i += 1
            elif ch == "/" and nxt == "*":
                in_block_comment = True
                i += 1
            elif ch in ('"', "'", "`"):
                in_string = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return source[: i + 1].count("\n") + 1

        i += 1

    return None


# ---------------------------------------------------------------------------
# Merge undersized adjacent chunks
# ---------------------------------------------------------------------------


def _merge_small_adjacent(
    chunks: Iterable[CodeChunk], *, min_tokens: int
) -> list[CodeChunk]:
    out: list[CodeChunk] = []
    pending: CodeChunk | None = None

    for chunk in chunks:
        if pending is None:
            pending = chunk
            continue

        same_file = chunk.file_path == pending.file_path
        same_lang = chunk.language == pending.language
        small_enough = pending.estimated_tokens < min_tokens
        adjacent = chunk.start_line >= pending.end_line  # always true given source order

        if same_file and same_lang and small_enough and adjacent:
            merged_text = pending.text + "\n\n" + chunk.text
            pending = CodeChunk(
                file_path=pending.file_path,
                language=pending.language,
                kind="merged",
                name=f"{pending.name}+{chunk.name}",
                start_line=pending.start_line,
                end_line=chunk.end_line,
                text=merged_text,
                children=(*pending.children, pending.name, chunk.name),
            )
        else:
            out.append(pending)
            pending = chunk

    if pending is not None:
        out.append(pending)

    return out


__all__ = [
    "CodeChunk",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MIN_TOKENS",
    "extract_chunks",
    "regex_fallback_limitations",
    "supported_languages",
]
