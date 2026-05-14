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
from .log_normalizer import normalize_logs
from .sandbox_images import get_sandbox_profile
from ..config import settings


@dataclass(frozen=True)
class ContainerResult:
    """Public result type consumed by pipeline.py."""

    stdout: str
    stderr: str
    exit_code: int | None
    version_mismatch: bool = False
    container_runtime_version: int | None = None


def _install_prelude(profile) -> str | None:
    """Shell snippet that installs the test runner + project deps for *profile*.

    Returns None when the language image already ships everything needed
    (e.g. Maven, where ``mvn test`` resolves its own dependencies).
    """
    if not profile.install_command:
        return None
    if profile.language == "python":
        return (
            "pip install --no-cache-dir pytest"
            " && ((test -f requirements.txt"
            " && pip install --no-cache-dir -r requirements.txt)"
            " || (test -f server/requirements.txt"
            " && pip install --no-cache-dir -r server/requirements.txt)"
            " || true)"
        )
    if profile.language in {"javascript", "typescript"}:
        return (
            "test -f package.json"
            " && npm ci --ignore-scripts"
            " || true"
        )
    return profile.install_command


def _build_shell_command(profile) -> list[str]:
    """Build a composite shell command from the sandbox profile.

    The command runs inside the container as ``sh -c "..."``.  Install
    commands are guarded by a file-existence check so they are skipped
    when the dependency manifest is absent.
    """
    parts: list[str] = ["cd /workspace/tests"]

    prelude = _install_prelude(profile)
    if prelude is not None:
        parts.append(prelude)

    # Expose server/ to sys.path so local packages (e.g. `app`) are importable
    # without being pip-installed, covering repos with a server/ subdirectory layout.
    if profile.language == "python":
        parts.append("PYTHONPATH=/workspace/tests/server " + profile.test_command)
    else:
        parts.append(profile.test_command)
    return ["sh", "-c", " && ".join(parts)]


async def run_container(
    language: str,
    student_repo_path: str,
    test_suite_path: str | None,
    *,
    timeout_seconds: int | None = None,
    discovered_command: str | None = None,
    discovered_working_dir: str = ".",
    required_version: int | None = None,
) -> ContainerResult:
    """Run tests against the student repo in a container.

    When *discovered_command* is provided (auto_discover mode), runs that
    command inside the student repo with no separate test suite mount.
    Otherwise (instructor_suite mode) mounts *test_suite_path* and runs the
    profile-defined command.

    *required_version* is passed to ``get_sandbox_profile`` so the best
    matching image is selected.  If no compatible image exists the highest
    available is used and ``ContainerResult.version_mismatch`` will be True.

    *timeout_seconds* overrides the profile's default budget when set;
    otherwise the per-language ``SandboxProfile.default_timeout_seconds``
    applies (Java/C++ need ~10 min, Python/JS only ~2 min).
    """
    profile, version_ok = get_sandbox_profile(language, required_version)
    effective_timeout = (
        timeout_seconds if timeout_seconds is not None else profile.default_timeout_seconds
    )

    if discovered_command is not None:
        # auto_discover: copy the read-only source into a writable tmpfs at
        # /workspace/build so the discovered command (mvn/gradle/pytest/jest/
        # cmake/...) can write its build artifacts in-place like normal.
        safe_dir = discovered_working_dir.lstrip("/") or "."

        # After the discovered command, dump any JUnit-format XML test reports
        # to stdout so the parser sees real per-test results.  Stdout-native
        # frameworks (pytest, jest, gtest) ignore this; Maven Surefire and
        # Gradle write XML to disk and need this extraction.
        extract_xml = (
            r' ; find . \( -path "*/target/surefire-reports/*.xml"'
            r' -o -path "*/build/test-results/*/*.xml"'
            r' -o -path "*/build/test-results/*.xml" \)'
            r' -exec cat {} \; 2>/dev/null'
        )
        prelude = _install_prelude(profile)
        prelude_clause = f" && {prelude}" if prelude else ""
        inner = (
            # cp -R (not -a) avoids preserving host ownership; cap_drop=ALL
            # strips CAP_CHOWN so `-a`'s ownership-preserve calls fail on Linux
            # bind mounts whose source files belong to a non-root host user.
            f"cp -R /workspace/source/. /workspace/build/"
            f" && cd /workspace/build/{safe_dir}"
            f"{prelude_clause}"
            f" && {discovered_command}"
            f"; maple_status=$?"
            f"{extract_xml}"
            f"; exit $maple_status"
        )
        command = ["sh", "-c", inner]
        volumes = {
            student_repo_path: {"bind": "/workspace/source", "mode": "ro"},
        }
    else:
        # instructor_suite: mount test suite separately (existing behavior)
        volumes = {
            student_repo_path: {"bind": "/workspace/student", "mode": "ro"},
            test_suite_path: {"bind": "/workspace/tests", "mode": "ro"},
        }
        command = _build_shell_command(profile)

    # Dummy env vars satisfy projects whose config layer (e.g. pydantic-settings)
    # requires variables to be present at module import time. Tests should mock
    # real services; these only let the module graph load.
    sandbox_environment = {
        "DATABASE_URL": "postgresql+asyncpg://sandbox:sandbox@localhost:5432/sandbox",
        "SECRET_KEY": "sandbox-secret-key-not-used-for-real-auth-padding",
        "GITHUB_PAT": "ghp_sandbox_placeholder",
        "APP_ENV": "test",
    }

    container_working_dir = "/workspace/build" if discovered_command is not None else profile.working_dir

    config = ContainerConfig(
        image=profile.image,
        command=command,
        volumes=volumes,
        environment=sandbox_environment,
        working_dir=container_working_dir,
        timeout=effective_timeout,
        network_disabled=settings.DOCKER_SANDBOX_NETWORK_DISABLED,
        # Resource budget comes from the per-language profile so compile-heavy
        # languages (Java, C++) get more memory and CPU than interpreted ones.
        mem_limit=profile.mem_limit,
        cpu_period=100_000,
        cpu_quota=profile.cpu_quota,
        # Security: no privilege escalation, drop every Linux capability
        security_opt=["no-new-privileges:true"],
        cap_drop=["ALL"],
        # Filesystem: root FS is read-only; grant writable tmpfs only where
        # test runners need it (/tmp for scratch, /root for package-manager
        # caches that can't be suppressed)
        read_only=True,
        tmpfs={
            "/tmp": "size=256m,mode=1777,exec",
            "/root": "size=768m",
            # auto_discover copies the read-only source here and runs the
            # discovered command in this writable workdir. Big enough for
            # source + compiled artifacts; sized to fit within host RAM.
            **(
                {"/workspace/build": "size=1g,exec"}
                if discovered_command is not None
                else {}
            ),
        },
    )

    result: _RunnerResult = await _docker_run(config)
    return ContainerResult(
        stdout=normalize_logs(result.stdout),
        stderr=normalize_logs(result.stderr),
        exit_code=result.exit_code,
        version_mismatch=not version_ok,
        container_runtime_version=profile.runtime_version,
    )
