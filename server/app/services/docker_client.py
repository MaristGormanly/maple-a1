"""High-level Docker client for the evaluation pipeline.

Bridges the pipeline's call signature to the low-level docker_runner module,
using sandbox profiles to resolve image names and test commands.

Design-doc references:
    - Section 8: "Define language-specific base images: Python/Pytest,
      Java/JUnit, JavaScript/Jest, TypeScript/Jest"
    - Section 8: "Implement Docker SDK integration: spin up ephemeral
      sibling containers via /var/run/docker.sock"
"""

from __future__ import annotations

from dataclasses import dataclass

from .docker_runner import ContainerConfig
from .docker_runner import ContainerResult as _RunnerResult
from .docker_runner import run_container as _docker_run
from .sandbox_images import get_sandbox_profile


@dataclass(frozen=True)
class ContainerResult:
    """Public result type consumed by pipeline.py."""

    stdout: str
    stderr: str
    exit_code: int


def _build_shell_command(profile) -> list[str]:
    """Build a composite shell command from the sandbox profile.

    The command runs inside the container as ``sh -c "..."``.  Install
    commands are guarded by a file-existence check so they are skipped
    when the dependency manifest is absent.
    """
    parts: list[str] = ["cd /workspace/tests"]

    if profile.install_command:
        if profile.language == "python":
            parts.append(
                "test -f requirements.txt"
                " && pip install --no-cache-dir -r requirements.txt"
                " || true"
            )
        elif profile.language in {"javascript", "typescript"}:
            parts.append(
                "test -f package.json"
                " && npm ci --ignore-scripts"
                " || true"
            )
        else:
            parts.append(profile.install_command)

    parts.append(profile.test_command)
    return ["sh", "-c", " && ".join(parts)]


async def run_container(
    language: str,
    student_repo_path: str,
    test_suite_path: str,
    *,
    timeout_seconds: int = 30,
) -> ContainerResult:
    """Run the instructor test suite against the student repo in a container.

    Resolves a ``SandboxProfile`` from *language*, mounts the student repo
    and test suite as read-only volumes, and delegates to the Docker runner.
    """
    profile = get_sandbox_profile(language)

    volumes = {
        student_repo_path: {"bind": "/workspace/student", "mode": "ro"},
        test_suite_path: {"bind": "/workspace/tests", "mode": "ro"},
    }

    command = _build_shell_command(profile)

    config = ContainerConfig(
        image=profile.image,
        command=command,
        volumes=volumes,
        working_dir=profile.working_dir,
        timeout=timeout_seconds,
        # Network: student code must not reach the internet
        network_disabled=True,
        # Memory: cap each container at 256 MB
        mem_limit="256m",
        # CPU: 50% of one core (quota/period = 0.5)
        cpu_period=100_000,
        cpu_quota=50_000,
        # Security: no privilege escalation, drop every Linux capability
        security_opt=["no-new-privileges:true"],
        cap_drop=["ALL"],
        # Filesystem: root FS is read-only; grant writable tmpfs only where
        # test runners need it (/tmp for scratch, /root for package-manager
        # caches that can't be suppressed)
        read_only=True,
        tmpfs={
            "/tmp": "size=64m,mode=1777",
            "/root": "size=64m",
        },
    )

    result: _RunnerResult = await _docker_run(config)
    return ContainerResult(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
    )
