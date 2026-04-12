from dataclasses import dataclass


@dataclass(frozen=True)
class ContainerResult:
    stdout: str
    stderr: str
    exit_code: int


async def run_container(
    image: str,
    student_repo_path: str,
    test_suite_path: str,
    *,
    timeout_seconds: int = 3600,
) -> ContainerResult:
    """Run the instructor test suite against the student repo in a container.

    Mounts (conceptually): student repo read-only at ``/workspace/student``,
    test suite read-only at ``/workspace/tests``. Security hardening and TTL
    enforcement belong in Jayden's Docker runtime; this layer stays mockable for
    unit tests until that integration lands.

    Parameters ``image``, ``timeout_seconds``, and host paths are accepted so the
    real implementation can delegate to the SDK without changing call sites.
    """
    del image, student_repo_path, test_suite_path, timeout_seconds
    return ContainerResult(
        stdout="",
        stderr="docker_client.run_container: Docker SDK not yet integrated",
        exit_code=1,
    )
