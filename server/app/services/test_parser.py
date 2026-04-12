"""Parse container stdout/stderr into structured test-result JSON.

Pure function — no database, no network, no FastAPI dependencies.
"""

from __future__ import annotations

import re

_MAX_RAW_LEN = 50_000


def parse_test_results(stdout: str, stderr: str, exit_code: int) -> dict:
    """Return a structured dict describing the test run.

    Detection order:
      1. Resource-constraint exit codes (137 = OOM, 124 = timeout).
      2. Framework detection from output patterns.
      3. Individual test-result parsing.
    """
    combined = (stdout or "") + "\n" + (stderr or "")
    truncated = len(combined) > _MAX_RAW_LEN

    resource_meta = _resource_constraint_metadata(exit_code)

    if not combined.strip():
        return _build(
            framework="unknown",
            tests=[],
            resource_constraint_metadata=resource_meta,
            raw_output_truncated=truncated,
        )

    if _looks_like_build_failure(combined):
        return _build(
            framework="unknown",
            tests=[
                {
                    "name": "build",
                    "status": "error",
                    "message": _first_error_line(combined),
                }
            ],
            resource_constraint_metadata=resource_meta,
            raw_output_truncated=truncated,
            errors_override=1,
        )

    for detector, parser in (
        (_detect_pytest, _parse_pytest),
        (_detect_junit, _parse_junit),
        (_detect_jest, _parse_jest),
    ):
        if detector(combined):
            tests = parser(combined)
            fw = detector.__name__.replace("_detect_", "")
            return _build(
                framework=fw,
                tests=tests,
                resource_constraint_metadata=resource_meta,
                raw_output_truncated=truncated,
            )

    return _build(
        framework="unknown",
        tests=[],
        resource_constraint_metadata=resource_meta,
        raw_output_truncated=truncated,
    )


def _resource_constraint_metadata(exit_code: int) -> dict | None:
    if exit_code == 137:
        return {"exit_code": 137, "oom_killed": True, "timed_out": False}
    if exit_code == 124:
        return {"exit_code": 124, "oom_killed": False, "timed_out": True}
    return None


def _build(
    *,
    framework: str,
    tests: list[dict],
    resource_constraint_metadata: dict | None,
    raw_output_truncated: bool,
    errors_override: int | None = None,
) -> dict:
    passed = sum(1 for t in tests if t["status"] == "passed")
    failed = sum(1 for t in tests if t["status"] == "failed")
    errors = errors_override if errors_override is not None else sum(
        1 for t in tests if t["status"] == "error"
    )
    skipped = sum(1 for t in tests if t["status"] == "skipped")
    return {
        "framework": framework,
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "skipped": skipped,
        "tests": tests,
        "resource_constraint_metadata": resource_constraint_metadata,
        "raw_output_truncated": raw_output_truncated,
    }


# ---------------------------------------------------------------------------
# Build-failure heuristic
# ---------------------------------------------------------------------------

_BUILD_PATTERNS = [
    re.compile(r"error:\s", re.IGNORECASE),
    re.compile(r"SyntaxError:", re.IGNORECASE),
    re.compile(r"ModuleNotFoundError:", re.IGNORECASE),
    re.compile(r"ImportError:", re.IGNORECASE),
    re.compile(r"compilation failed", re.IGNORECASE),
    re.compile(r"BUILD FAILED", re.IGNORECASE),
]

_FRAMEWORK_MARKERS = [
    re.compile(r"=+\s*(FAILURES|ERRORS|short test summary|passed|failed)\s*=+", re.IGNORECASE),
    re.compile(r"<testsuite\b"),
    re.compile(r"Tests?:\s+\d+\s+(passed|failed)", re.IGNORECASE),
    re.compile(r"Test Suites?:", re.IGNORECASE),
]


def _looks_like_build_failure(text: str) -> bool:
    has_build_error = any(p.search(text) for p in _BUILD_PATTERNS)
    has_framework = any(p.search(text) for p in _FRAMEWORK_MARKERS)
    return has_build_error and not has_framework


def _first_error_line(text: str) -> str:
    for line in text.splitlines():
        for p in _BUILD_PATTERNS:
            if p.search(line):
                return line.strip()
    return "build error"


# ---------------------------------------------------------------------------
# Pytest
# ---------------------------------------------------------------------------

_PYTEST_SUMMARY = re.compile(
    r"=+\s*(?:(?P<counts>[^=]+)\s+in\s+[\d.]+s)\s*=+",
)
_PYTEST_COUNT = re.compile(r"(\d+)\s+(passed|failed|error|skipped|warnings?)")
_PYTEST_RESULT_LINE = re.compile(
    r"^(PASSED|FAILED|ERROR)\s+(.+?)(?:\s+-\s+(.+))?$", re.MULTILINE,
)
_PYTEST_VERBOSE = re.compile(
    r"^(.+?)\s+(PASSED|FAILED|ERROR|SKIPPED)\s*(?:\[.*\])?\s*$", re.MULTILINE,
)


def _detect_pytest(text: str) -> bool:
    return bool(
        _PYTEST_SUMMARY.search(text)
        or re.search(r"=+ short test summary info =+", text)
        or re.search(r"=+ FAILURES =+", text)
        or re.search(r"=+ ERRORS =+", text)
        or re.search(r"pytest", text, re.IGNORECASE)
        and re.search(r"passed|failed", text, re.IGNORECASE)
    )


def _parse_pytest(text: str) -> list[dict]:
    tests: list[dict] = []
    for m in _PYTEST_VERBOSE.finditer(text):
        name = m.group(1).strip()
        raw_status = m.group(2).upper()
        status = {"PASSED": "passed", "FAILED": "failed", "ERROR": "error", "SKIPPED": "skipped"}.get(
            raw_status, "error"
        )
        tests.append({"name": name, "status": status, "message": None})

    if not tests:
        for m in _PYTEST_RESULT_LINE.finditer(text):
            raw_status = m.group(1).upper()
            status = {"PASSED": "passed", "FAILED": "failed", "ERROR": "error"}.get(raw_status, "error")
            tests.append({"name": m.group(2).strip(), "status": status, "message": m.group(3)})

    return tests


# ---------------------------------------------------------------------------
# JUnit XML
# ---------------------------------------------------------------------------

_JUNIT_SUITE = re.compile(
    r'<testsuite\b[^>]*\btests="(?P<tests>\d+)"[^>]*'
    r'\bfailures="(?P<failures>\d+)"[^>]*'
    r'(?:\berrors="(?P<errors>\d+)")?[^>]*>',
    re.DOTALL,
)
_JUNIT_CASE = re.compile(
    r'<testcase\b[^>]*\bname="(?P<name>[^"]*)"[^>]*(?<!/)>(?P<body>.*?)</testcase>',
    re.DOTALL,
)
_JUNIT_CASE_SELF_CLOSING = re.compile(
    r'<testcase\b[^>]*\bname="(?P<name>[^"]*)"[^>]*/\s*>',
    re.DOTALL,
)


def _detect_junit(text: str) -> bool:
    return "<testsuite" in text


def _parse_junit(text: str) -> list[dict]:
    tests: list[dict] = []
    for m in _JUNIT_CASE.finditer(text):
        name = m.group("name")
        body = m.group("body")
        if "<failure" in body:
            msg_m = re.search(r'message="([^"]*)"', body)
            tests.append({
                "name": name,
                "status": "failed",
                "message": msg_m.group(1) if msg_m else None,
            })
        elif "<error" in body:
            tests.append({"name": name, "status": "error", "message": None})
        elif "<skipped" in body:
            tests.append({"name": name, "status": "skipped", "message": None})
        else:
            tests.append({"name": name, "status": "passed", "message": None})

    for m in _JUNIT_CASE_SELF_CLOSING.finditer(text):
        name = m.group("name")
        if not any(t["name"] == name for t in tests):
            tests.append({"name": name, "status": "passed", "message": None})

    return tests


# ---------------------------------------------------------------------------
# Jest
# ---------------------------------------------------------------------------

_JEST_SUMMARY = re.compile(
    r"Tests?:\s+(?:(\d+)\s+failed,?\s*)?(?:(\d+)\s+passed,?\s*)?(\d+)\s+total",
    re.IGNORECASE,
)
_JEST_LINE = re.compile(
    r"^\s+(✓|✕|✗|√|×)\s+(.+?)(?:\s+\([\d.]+\s*m?s\))?\s*$",
    re.MULTILINE,
)


def _detect_jest(text: str) -> bool:
    return bool(
        _JEST_SUMMARY.search(text)
        or re.search(r"Test Suites?:", text)
    )


def _parse_jest(text: str) -> list[dict]:
    tests: list[dict] = []
    for m in _JEST_LINE.finditer(text):
        marker = m.group(1)
        name = m.group(2).strip()
        if marker in {"✓", "√", "PASS"}:
            tests.append({"name": name, "status": "passed", "message": None})
        else:
            tests.append({"name": name, "status": "failed", "message": None})
    return tests
