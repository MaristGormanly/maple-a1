"""Language-specific sandbox image profiles for container execution.

Each supported language maps to a SandboxProfile that defines the Docker
image, dependency install command, and test runner command used inside
ephemeral containers.

Design-doc references:
    - Section 8: "Define language-specific base images: Python/Pytest,
      Java/JUnit, JavaScript/Jest, TypeScript/Jest"
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxProfile:
    """Language-specific sandbox configuration for container execution."""

    language: str
    image: str
    install_command: str | None
    test_command: str
    working_dir: str


SANDBOX_PROFILES: dict[str, SandboxProfile] = {
    "python": SandboxProfile(
        language="python",
        image="python:3.12-slim",
        install_command="pip install --no-cache-dir -r requirements.txt",
        test_command="python -m pytest --tb=short -v --continue-on-collection-errors",
        working_dir="/workspace",
    ),
    "java": SandboxProfile(
        language="java",
        image="maven:3.9-eclipse-temurin-17",
        install_command=None,
        test_command=(
            "mvn test -B -Djava.io.tmpdir=/workspace 2>&1"
            "; find target/surefire-reports -name '*.xml' -exec cat {} \\; 2>/dev/null"
        ),
        working_dir="/workspace",
    ),
    "javascript": SandboxProfile(
        language="javascript",
        image="node:20-slim",
        install_command="npm ci --ignore-scripts",
        test_command="npx jest --verbose",
        working_dir="/workspace",
    ),
    "typescript": SandboxProfile(
        language="typescript",
        image="node:20-slim",
        install_command="npm ci --ignore-scripts",
        test_command="npx jest --verbose",
        working_dir="/workspace",
    ),
    "cpp": SandboxProfile(
        language="cpp",
        image="ubuntu:22.04",
        install_command="apt-get update -qq && apt-get install -y -qq cmake g++ libgtest-dev 2>/dev/null",
        test_command=(
            "mkdir -p build"
            " && cmake -S . -B build -DCMAKE_BUILD_TYPE=Debug 2>&1"
            " && cmake --build build --parallel 2>&1"
            " && cd build && ctest --output-on-failure 2>&1"
        ),
        working_dir="/workspace",
    ),
}

DEFAULT_PROFILE = SANDBOX_PROFILES["python"]


def get_sandbox_profile(language: str) -> SandboxProfile:
    """Return the sandbox profile for *language*, falling back to DEFAULT_PROFILE."""
    return SANDBOX_PROFILES.get((language or "").lower(), DEFAULT_PROFILE)


@dataclass(frozen=True)
class LintProfile:
    """Language-specific linter configuration for static analysis in containers."""

    language: str
    image: str          # e.g. maple-python-lint:3.12
    command: list[str]  # command to run inside container


LINT_PROFILES: dict[str, LintProfile] = {
    "python": LintProfile(
        language="python",
        image="maple-python-lint:3.12",
        command=["pylint", "--output-format=json", "--recursive=y", "."],
    ),
    "javascript": LintProfile(
        language="javascript",
        image="maple-node-lint:20",
        command=["eslint", "--format=json", "."],
    ),
    "typescript": LintProfile(
        language="typescript",
        image="maple-node-lint:20",
        command=["eslint", "--format=json", "."],
    ),
}


def get_lint_profile(language: str) -> LintProfile | None:
    """Return the lint profile for *language*, or None if unsupported."""
    return LINT_PROFILES.get((language or "").lower())
