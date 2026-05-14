"""
Docker container runner service for MAPLE A1.

Milestone 2 scope: Provides ephemeral sibling container execution via
/var/run/docker.sock. No Docker-in-Docker — containers run as siblings
on the host Docker daemon.

Design-doc references:
    - Section 6: "direct access to the Docker Daemon via /var/run/docker.sock"
    - Section 8: "spin up ephemeral sibling containers via /var/run/docker.sock"
    - Section 2: "spin up ephemeral, highly restricted containers ... captures
      the output as structured JSON, and immediately destroys the container"
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import docker
from docker.errors import APIError, DockerException, ImageNotFound

from ..config import PROJECT_ROOT, settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data transfer objects
# ---------------------------------------------------------------------------

@dataclass
class ContainerConfig:
    """Input parameters for running an ephemeral container."""

    image: str
    command: str | list[str]
    volumes: dict[str, dict[str, str]] = field(default_factory=dict)
    environment: dict[str, str] = field(default_factory=dict)
    working_dir: str | None = None
    timeout: int | None = None
    network_disabled: bool = False
    # Resource limits (Task 4)
    mem_limit: str | None = None
    cpu_period: int | None = None
    cpu_quota: int | None = None
    # Security hardening (Task 4)
    cap_drop: list[str] = field(default_factory=list)
    security_opt: list[str] = field(default_factory=list)
    read_only: bool = False
    tmpfs: dict[str, str] = field(default_factory=dict)


@dataclass
class ContainerResult:
    """Output from an ephemeral container run."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class DockerRunnerError(Exception):
    """Raised when container execution fails for infrastructure reasons."""


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _get_client() -> docker.DockerClient:
    """Create a Docker client connected to the configured socket."""
    return docker.DockerClient(base_url=settings.DOCKER_SOCKET_URL)


def _host_volume_source(source: str) -> str:
    """Translate in-container project paths to host paths for sibling containers."""
    host_root = getattr(settings, "DOCKER_HOST_PROJECT_ROOT", "")
    if not isinstance(host_root, str) or not host_root.strip():
        return source

    source_path = Path(source)
    if not source_path.is_absolute():
        return source

    try:
        relative_source = source_path.resolve().relative_to(PROJECT_ROOT.resolve())
    except ValueError:
        return source

    return str(Path(host_root.strip()) / relative_source)


def _host_volume_sources(volumes: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    return {_host_volume_source(source): options for source, options in volumes.items()}


# ---------------------------------------------------------------------------
# Synchronous container lifecycle
# ---------------------------------------------------------------------------

def _run_container_sync(config: ContainerConfig) -> ContainerResult:
    """Execute the full container lifecycle: create -> start -> wait -> logs -> remove.

    The container is ALWAYS removed in the ``finally`` block to guarantee
    ephemeral behaviour regardless of success or failure.
    """
    client = _get_client()
    container = None
    timeout = config.timeout if config.timeout is not None else settings.DOCKER_CONTAINER_TIMEOUT

    # Build create kwargs, omitting None values so the Docker API uses its
    # own defaults rather than receiving explicit nulls.
    create_kwargs: dict = {
        "image": config.image,
        "command": config.command,
        "detach": True,
    }
    if config.volumes:
        create_kwargs["volumes"] = _host_volume_sources(config.volumes)
    if config.environment:
        create_kwargs["environment"] = config.environment
    if config.working_dir is not None:
        create_kwargs["working_dir"] = config.working_dir
    if config.network_disabled:
        create_kwargs["network_disabled"] = True
    if config.mem_limit is not None:
        create_kwargs["mem_limit"] = config.mem_limit
    if config.cpu_period is not None:
        create_kwargs["cpu_period"] = config.cpu_period
    if config.cpu_quota is not None:
        create_kwargs["cpu_quota"] = config.cpu_quota
    if config.cap_drop:
        create_kwargs["cap_drop"] = config.cap_drop
    if config.security_opt:
        create_kwargs["security_opt"] = config.security_opt
    if config.read_only:
        create_kwargs["read_only"] = True
    if config.tmpfs:
        create_kwargs["tmpfs"] = config.tmpfs

    try:
        try:
            logger.info(
                "docker_runner: creating sandbox container image=%s "
                "timeout=%s network_disabled=%s",
                config.image,
                timeout,
                config.network_disabled,
            )
            container = client.containers.create(**create_kwargs)
        except ImageNotFound:
            logger.info("Image %s not found locally; pulling from registry...", config.image)
            try:
                client.images.pull(config.image)
            except (ImageNotFound, APIError):
                raise DockerRunnerError(
                    f"Image {config.image!r} not found locally and could not be pulled from registry"
                ) from None
            logger.info("docker_runner: pulled sandbox image=%s", config.image)
            container = client.containers.create(**create_kwargs)
        container_id = getattr(container, "id", "unknown")
        logger.info(
            "docker_runner: sandbox container created id=%s image=%s",
            container_id,
            config.image,
        )
        container.start()
        started_at = time.monotonic()
        logger.info(
            "docker_runner: sandbox container started id=%s image=%s",
            container_id,
            config.image,
        )

        wait_result = container.wait(timeout=timeout)
        exit_code: int = wait_result["StatusCode"]
        elapsed_s = time.monotonic() - started_at
        logger.info(
            "docker_runner: sandbox container finished id=%s image=%s "
            "exit_code=%s elapsed_s=%.1f",
            container_id,
            config.image,
            exit_code,
            elapsed_s,
        )

        stdout = container.logs(stdout=True, stderr=False).decode(
            "utf-8", errors="replace"
        )
        stderr = container.logs(stdout=False, stderr=True).decode(
            "utf-8", errors="replace"
        )

        return ContainerResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
        )

    except (DockerException, APIError, ImageNotFound) as exc:
        raise DockerRunnerError(f"Container execution failed: {exc}") from exc

    except Exception:
        # Likely a timeout from container.wait(). Try to kill and collect logs.
        if container is not None:
            try:
                container.kill()
                stdout = container.logs(stdout=True, stderr=False).decode(
                    "utf-8", errors="replace"
                )
                stderr = container.logs(stdout=False, stderr=True).decode(
                    "utf-8", errors="replace"
                )
                logger.warning(
                    "docker_runner: sandbox container timed out and was killed "
                    "id=%s image=%s timeout_s=%s stdout_bytes=%d stderr_bytes=%d",
                    getattr(container, "id", "unknown"),
                    config.image,
                    timeout,
                    len(stdout),
                    len(stderr),
                )
                return ContainerResult(
                    # TTL exceeded; test_parser maps this to timed_out=True.
                    exit_code=124,
                    stdout=stdout,
                    stderr=stderr,
                    timed_out=True,
                )
            except Exception as kill_exc:
                raise DockerRunnerError(
                    f"Container timed out and could not be killed: {kill_exc}"
                ) from kill_exc
        raise

    finally:
        if container is not None:
            try:
                container.remove(force=True)
                logger.info(
                    "docker_runner: sandbox container removed id=%s image=%s",
                    getattr(container, "id", "unknown"),
                    config.image,
                )
            except Exception:
                logger.warning("Failed to remove container %s", getattr(container, "id", "unknown"))
        client.close()


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------

async def run_container(config: ContainerConfig) -> ContainerResult:
    """Run an ephemeral container asynchronously.

    Offloads the blocking Docker SDK calls to a thread via
    ``asyncio.to_thread`` so the FastAPI event loop is not blocked.
    """
    return await asyncio.to_thread(_run_container_sync, config)
