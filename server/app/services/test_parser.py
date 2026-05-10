"""Parse container stdout/stderr into structured test-result JSON.

Pure function — no database, no network, no FastAPI dependencies.
"""

from __future__ import annotations

import re

_MAX_RAW_LEN = 50_000


def parse_test_results(stdout: str, stderr: str, exit_code: int | None) -> dict:
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
        is_version_mismatch = any(p.search(combined) for p in _VERSION_MISMATCH_PATTERNS)
        build_test: dict = {
            "name": "build",
            "status": "error",
            "message": _first_error_line(combined),
        }
        if is_version_mismatch:
            build_test["build_error_type"] = "version_mismatch"
        return _build(
            framework="unknown",
            tests=[build_test],
            resource_constraint_metadata=resource_meta,
            raw_output_truncated=truncated,
            errors_override=1,
        )

    for detector, parser in (
        (_detect_pytest, _parse_pytest),
        (_detect_junit, _parse_junit),
        (_detect_jest, _parse_jest),
        (_detect_gtest, _parse_gtest),
        (_detect_gradle, _parse_gradle),
        (_detect_maven_surefire, _parse_maven_surefire),
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


def _resource_constraint_metadata(exit_code: int | None) -> dict | None:
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

# Patterns that indicate a runtime/compiler version mismatch specifically.
# Matched after _BUILD_PATTERNS confirms a build error — used to set build_error_type.
_VERSION_MISMATCH_PATTERNS = [
    re.compile(r"release version \d+ not supported", re.IGNORECASE),        # javac
    re.compile(r"Source option \d+ is not supported", re.IGNORECASE),        # javac
    re.compile(r"Target option \d+ is not supported", re.IGNORECASE),        # javac
    re.compile(r"unsupported class file major version", re.IGNORECASE),      # JVM class load
    re.compile(r"Python \d+\.\d+ is not supported", re.IGNORECASE),         # Python
    re.compile(r'The engine "node" is incompatible', re.IGNORECASE),         # Node/yarn
    re.compile(r"error: release", re.IGNORECASE),                            # javac shorthand
    re.compile(r"\[MAPLE\] Version mismatch", re.IGNORECASE),               # pipeline annotation
]

_FRAMEWORK_MARKERS = [
    re.compile(r"=+\s*(FAILURES|ERRORS|short test summary|passed|failed)\s*=+", re.IGNORECASE),
    # Pytest summary line, e.g. "=== 7 failed, 102 passed, 23 errors in 3.20s ==="
    re.compile(r"=+[^=\n]*\d+\s+(passed|failed|error|skipped)[^=\n]*=+", re.IGNORECASE),
    re.compile(r"<testsuite\b"),
    re.compile(r"Tests?:\s+\d+\s+(passed|failed)", re.IGNORECASE),
    re.compile(r"Test Suites?:", re.IGNORECASE),
    # Gradle: "> Task :test" or per-test "ClassName > method PASSED|FAILED|SKIPPED"
    re.compile(r"^>\s+Task\s+:.*?\btest\b", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^[\w.$]+\s+>\s+.+?\s+(PASSED|FAILED|SKIPPED)\s*$", re.MULTILINE),
    # Maven Surefire per-class summary
    re.compile(r"\[(?:INFO|ERROR)\]\s+Tests run:\s*\d+,\s*Failures:\s*\d+", re.IGNORECASE),
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
_PYTEST_FAIL_SUMMARY_LINE = re.compile(
    r"^(?:FAILED|ERROR)\s+(.+?)\s+-\s+(.+)$", re.MULTILINE
)
_PYTEST_VERBOSE = re.compile(
    r"^(.+?)\s+(PASSED|FAILED|ERROR|SKIPPED)\s*(?:\[.*\])?\s*$", re.MULTILINE,
)


def _parse_pytest_failure_messages(text: str) -> dict[str, str]:
    """Extract {test_name: error_message} from pytest short test summary lines."""
    result: dict[str, str] = {}
    for m in _PYTEST_FAIL_SUMMARY_LINE.finditer(text):
        result[m.group(1).strip()] = m.group(2).strip()
    return result


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

    # Enrich failed/error tests with one-liner messages from the short summary section.
    failure_msgs = _parse_pytest_failure_messages(text)
    if failure_msgs:
        for t in tests:
            if t["status"] in ("failed", "error") and t["message"] is None:
                name = t["name"]
                msg = failure_msgs.get(name)
                if msg is None:
                    for k, v in failure_msgs.items():
                        if name.endswith(k) or k.endswith(name):
                            msg = v
                            break
                t["message"] = msg

    # Reconcile with the pytest summary line so truncated logs (log_normalizer
    # drops the middle of long traces) still produce accurate aggregate counts.
    summary = _PYTEST_SUMMARY.search(text)
    if summary:
        summary_counts: dict[str, int] = {}
        for cm in _PYTEST_COUNT.finditer(summary.group("counts") or ""):
            n = int(cm.group(1))
            status = cm.group(2).rstrip("s")
            if status in {"passed", "failed", "error", "skipped"}:
                summary_counts[status] = n

        extracted: dict[str, int] = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
        for t in tests:
            extracted[t["status"]] = extracted.get(t["status"], 0) + 1

        for status, total in summary_counts.items():
            missing = total - extracted.get(status, 0)
            for i in range(missing):
                tests.append({"name": f"truncated-{status}-{i}", "status": status, "message": None})

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


# ---------------------------------------------------------------------------
# Google Test (C++)
# ---------------------------------------------------------------------------

_GTEST_DETECT = re.compile(r"^\[={10,}\] Running \d+ tests? from", re.MULTILINE)
_GTEST_OK     = re.compile(r"^\[\s+OK\s+\]\s+(.+?)(?:\s+\(\d+ ms\))?$", re.MULTILINE)
_GTEST_FAIL   = re.compile(r"^\[\s+FAILED\s+\]\s+(.+?)(?:\s+\(\d+ ms\))?$", re.MULTILINE)


def _detect_gtest(text: str) -> bool:
    return bool(_GTEST_DETECT.search(text))


def _parse_gtest(text: str) -> list[dict]:
    tests: list[dict] = []
    for m in _GTEST_OK.finditer(text):
        tests.append({"name": m.group(1).strip(), "status": "passed", "message": None})
    for m in _GTEST_FAIL.finditer(text):
        tests.append({"name": m.group(1).strip(), "status": "failed", "message": None})
    return tests


# ---------------------------------------------------------------------------
# Gradle (text output — used when Gradle's JUnit XML isn't extracted)
# ---------------------------------------------------------------------------

_GRADLE_DETECT = re.compile(
    r"^>\s+Task\s+:.*?\btest\b|BUILD\s+(?:SUCCESSFUL|FAILED)",
    re.MULTILINE | re.IGNORECASE,
)
# Matches lines like:
#   "com.example.MyTest > shouldDoFoo() PASSED"
#   "com.example.MyTest > shouldDoFoo() FAILED"
#   "com.example.MyTest > shouldDoFoo() SKIPPED"
_GRADLE_TEST_LINE = re.compile(
    r"^([\w.$]+(?:\.[\w.$]+)+)\s+>\s+(.+?)\s+(PASSED|FAILED|SKIPPED)(?:\s|$)",
    re.MULTILINE,
)


def _detect_gradle(text: str) -> bool:
    return bool(_GRADLE_DETECT.search(text))


def _parse_gradle(text: str) -> list[dict]:
    tests: list[dict] = []
    for m in _GRADLE_TEST_LINE.finditer(text):
        cls = m.group(1).strip()
        method = m.group(2).strip()
        raw = m.group(3).upper()
        status = {"PASSED": "passed", "FAILED": "failed", "SKIPPED": "skipped"}.get(raw, "error")
        tests.append({
            "name": f"{cls} > {method}",
            "status": status,
            "message": None,
        })
    return tests


# ---------------------------------------------------------------------------
# Maven Surefire (text output fallback — used when surefire XML is absent)
# ---------------------------------------------------------------------------

# Per-class summary line emitted by Maven for each test class
_MAVEN_CLASS_LINE = re.compile(
    r"\[(?:INFO|ERROR|WARNING)\]\s+Tests run:\s*(\d+),\s*Failures:\s*(\d+),"
    r"\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)"
    r"(?:.*?-\s+in\s+(\S+))?",
    re.IGNORECASE,
)
# Per-method failure marker: "[ERROR]  ClassName.methodName -- Time elapsed: ... <<< FAILURE!"
_MAVEN_METHOD_FAIL = re.compile(
    r"\[ERROR\]\s+(\S+\.\S+)\s+--\s+Time elapsed:.*<<<\s*(FAILURE|ERROR)!",
    re.IGNORECASE,
)


def _detect_maven_surefire(text: str) -> bool:
    return bool(_MAVEN_CLASS_LINE.search(text))


def _parse_maven_surefire(text: str) -> list[dict]:
    """Parse Maven's per-class text summary into individual test entries.

    When surefire XML lands in stdout (via the find/cat append), the JUnit
    parser takes precedence.  This handles the fallback case where only the
    Maven console summary is available.
    """
    # Collect per-method failures for richer naming
    failed_methods: dict[str, str] = {}
    for m in _MAVEN_METHOD_FAIL.finditer(text):
        fq_name = m.group(1).strip()
        status = "failed" if m.group(2).upper() == "FAILURE" else "error"
        failed_methods[fq_name] = status

    tests: list[dict] = []
    for m in _MAVEN_CLASS_LINE.finditer(text):
        total = int(m.group(1))
        failures = int(m.group(2))
        errors = int(m.group(3))
        skipped = int(m.group(4))
        cls = (m.group(5) or "unknown").strip()
        passed = max(0, total - failures - errors - skipped)

        for i in range(passed):
            tests.append({"name": f"{cls}#{i + 1}", "status": "passed", "message": None})
        for i in range(failures):
            tests.append({"name": f"{cls}#fail{i + 1}", "status": "failed", "message": None})
        for i in range(errors):
            tests.append({"name": f"{cls}#error{i + 1}", "status": "error", "message": None})
        for i in range(skipped):
            tests.append({"name": f"{cls}#skip{i + 1}", "status": "skipped", "message": None})

    # Upgrade synthetic entries to named ones where we have per-method detail
    fail_iter = iter(
        (name, st) for name, st in failed_methods.items()
        if any(name.startswith(t["name"].rsplit("#", 1)[0]) for t in tests)
    )
    for t in tests:
        if t["status"] in ("failed", "error"):
            try:
                real_name, real_status = next(fail_iter)
                t["name"] = real_name
                t["status"] = real_status
            except StopIteration:
                break

    return tests
