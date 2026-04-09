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
from dataclasses import dataclass, field

import docker
from docker.errors import APIError, DockerException, ImageNotFound

from ..config import settings

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
    # Resource limits — Task 4 (security hardening) will set these.
    mem_limit: str | None = None
    cpu_period: int | None = None
    cpu_quota: int | None = None


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
        create_kwargs["volumes"] = config.volumes
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

    try:
        container = client.containers.create(**create_kwargs)
        container.start()

        wait_result = container.wait(timeout=timeout)
        exit_code: int = wait_result["StatusCode"]

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
                return ContainerResult(
                    exit_code=-1,
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
