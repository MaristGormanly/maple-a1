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
        test_command="pytest --tb=short -v",
        working_dir="/workspace",
    ),
    "java": SandboxProfile(
        language="java",
        image="maven:3.9-openjdk-17-slim",
        install_command=None,
        test_command="mvn test -B",
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
}

DEFAULT_PROFILE = SANDBOX_PROFILES["python"]


def get_sandbox_profile(language: str) -> SandboxProfile:
    """Return the sandbox profile for *language*, falling back to DEFAULT_PROFILE."""
    return SANDBOX_PROFILES.get((language or "").lower(), DEFAULT_PROFILE)
