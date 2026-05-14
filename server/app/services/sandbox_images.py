"""Language-specific sandbox image profiles for container execution.

Each supported language maps to a SandboxProfile that defines the Docker
image, dependency install command, and test runner command used inside
ephemeral containers.

Design-doc references:
    - Section 8: "Define language-specific base images: Python/Pytest,
      Java/JUnit, JavaScript/Jest, TypeScript/Jest"
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class SandboxProfile:
    """Language-specific sandbox configuration for container execution."""

    language: str
    image: str
    install_command: str | None
    test_command: str
    working_dir: str
    runtime_version: int | None = field(default=None)
    # runtime_version encoding:
    #   Java/Node: major integer (e.g. 21, 17, 11, 20, 18)
    #   Python: major*100 + minor (e.g. 312 = 3.12, 311 = 3.11)
    # Resource budget. Compile-heavy languages (Java, C++) override these;
    # interpreted languages keep the defaults.
    default_timeout_seconds: int = 120
    mem_limit: str = "256m"
    cpu_quota: int = 50_000  # 0.5 CPU at the standard 100_000 cpu_period
    # C++ needs read_only=False so apt-get can write to /var/lib/dpkg and
    # /var/lib/apt/lists; all other languages run with a read-only root FS.
    read_only: bool = True


_JAVA_TEST_COMMAND = (
    "mvn test -B -Djava.io.tmpdir=/workspace 2>&1"
    "; maple_status=$?"
    "; find target/surefire-reports -name '*.xml' -exec cat {} \\; 2>/dev/null"
    "; exit $maple_status"
)

# Empirically derived from a prod probe of TheAlgorithms/Java (746 test files,
# 9267 tests): full mvn test finished in 4m33s at 2 GB / 1 CPU. Smaller Maven
# projects fit comfortably; allow 10 minutes for projects with heavier deps.
_JAVA_BUDGET: dict[str, int | str] = {
    "default_timeout_seconds": 600,
    "mem_limit": "2g",
    "cpu_quota": 100_000,  # 1 full CPU
}

_JAVA_PROFILES: list[SandboxProfile] = [
    SandboxProfile(
        language="java",
        image="maven:3.9-eclipse-temurin-8",
        install_command=None,
        test_command=_JAVA_TEST_COMMAND,
        working_dir="/workspace",
        runtime_version=8,
        **_JAVA_BUDGET,
    ),
    SandboxProfile(
        language="java",
        image="maven:3.9-eclipse-temurin-11",
        install_command=None,
        test_command=_JAVA_TEST_COMMAND,
        working_dir="/workspace",
        runtime_version=11,
        **_JAVA_BUDGET,
    ),
    SandboxProfile(
        language="java",
        image="maven:3.9-eclipse-temurin-17",
        install_command=None,
        test_command=_JAVA_TEST_COMMAND,
        working_dir="/workspace",
        runtime_version=17,
        **_JAVA_BUDGET,
    ),
    SandboxProfile(
        language="java",
        image="maven:3.9-eclipse-temurin-21",
        install_command=None,
        test_command=_JAVA_TEST_COMMAND,
        working_dir="/workspace",
        runtime_version=21,
        **_JAVA_BUDGET,
    ),
]

_PYTHON_PROFILES: list[SandboxProfile] = [
    SandboxProfile(
        language="python",
        image="python:3.10-slim",
        install_command="pip install --no-cache-dir -r requirements.txt",
        test_command="python -m pytest --tb=short -v --continue-on-collection-errors",
        working_dir="/workspace",
        runtime_version=310,
    ),
    SandboxProfile(
        language="python",
        image="python:3.11-slim",
        install_command="pip install --no-cache-dir -r requirements.txt",
        test_command="python -m pytest --tb=short -v --continue-on-collection-errors",
        working_dir="/workspace",
        runtime_version=311,
    ),
    SandboxProfile(
        language="python",
        image="python:3.12-slim",
        install_command="pip install --no-cache-dir -r requirements.txt",
        test_command="python -m pytest --tb=short -v --continue-on-collection-errors",
        working_dir="/workspace",
        runtime_version=312,
    ),
]

_NODE_PROFILES: list[SandboxProfile] = [
    SandboxProfile(
        language="javascript",
        image="node:18-slim",
        install_command="npm ci --ignore-scripts",
        test_command="npx jest --verbose",
        working_dir="/workspace",
        runtime_version=18,
    ),
    SandboxProfile(
        language="javascript",
        image="node:20-slim",
        install_command="npm ci --ignore-scripts",
        test_command="npx jest --verbose",
        working_dir="/workspace",
        runtime_version=20,
    ),
    SandboxProfile(
        language="javascript",
        image="node:22-slim",
        install_command="npm ci --ignore-scripts",
        test_command="npx jest --verbose",
        working_dir="/workspace",
        runtime_version=22,
    ),
]

_TYPESCRIPT_PROFILES: list[SandboxProfile] = [
    replace(profile, language="typescript") for profile in _NODE_PROFILES
]

_CPP_PROFILE = SandboxProfile(
    language="cpp",
    image="maple-cpp-sandbox:22.04",
    install_command=None,
    test_command=(
        "mkdir -p build"
        " && cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug -DBUILD_TESTS=ON -DBUILD_TESTING=ON 2>&1"
        " && cmake --build build --parallel 2 2>&1"
        " && cd build && ctest --output-on-failure --verbose 2>&1"
    ),
    working_dir="/workspace",
    runtime_version=None,
    # Large C++ projects like ETLCPP compile hundreds of translation units
    # before tests run.  They need a wider budget than Java/Maven.
    default_timeout_seconds=1800,
    mem_limit="2g",
    cpu_quota=200_000,
)

# Per-language profile lists (ordered ascending by runtime_version).
_PROFILES_BY_LANGUAGE: dict[str, list[SandboxProfile]] = {
    "java": _JAVA_PROFILES,
    "python": _PYTHON_PROFILES,
    "javascript": _NODE_PROFILES,
    "typescript": _TYPESCRIPT_PROFILES,
}

# Default profile per language (highest version / most capable).
_DEFAULTS: dict[str, SandboxProfile] = {
    "java": _JAVA_PROFILES[-1],
    "python": _PYTHON_PROFILES[-1],
    "javascript": _NODE_PROFILES[1],   # node:20 is current LTS default
    "typescript": _TYPESCRIPT_PROFILES[1],
    "cpp": _CPP_PROFILE,
}

# Flat dict kept for backward-compat callers (linter path, tests, etc.)
SANDBOX_PROFILES: dict[str, SandboxProfile] = {k: v for k, v in _DEFAULTS.items()}
DEFAULT_PROFILE = SANDBOX_PROFILES["python"]


def get_sandbox_profile(
    language: str,
    required_version: int | None = None,
) -> tuple[SandboxProfile, bool]:
    """Return ``(profile, version_compatible)`` for *language*.

    *required_version* uses the same encoding as ``SandboxProfile.runtime_version``:
    Java/Node = major int, Python = major*100 + minor.

    Selects the lowest available version that satisfies ``>= required_version``.
    If no profile meets the requirement, falls back to the highest available and
    returns ``version_compatible=False``.

    When *required_version* is None, returns the language default with
    ``version_compatible=True``.
    """
    lang = (language or "").lower()
    profiles = _PROFILES_BY_LANGUAGE.get(lang)

    if not profiles:
        default = _DEFAULTS.get(lang, DEFAULT_PROFILE)
        return default, True

    if required_version is None:
        return _DEFAULTS[lang], True

    for profile in profiles:  # ascending order
        if profile.runtime_version is not None and profile.runtime_version >= required_version:
            return profile, True

    # No profile satisfies the requirement — use highest available.
    return profiles[-1], False
