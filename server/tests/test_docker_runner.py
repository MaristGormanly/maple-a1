"""Unit tests for the docker_runner service module."""

import unittest
from unittest.mock import MagicMock, patch

from app.services.docker_runner import (
    ContainerConfig,
    ContainerResult,
    DockerRunnerError,
    _run_container_sync,
)


def _make_mock_container(exit_code=0, stdout=b"", stderr=b""):
    """Return a MagicMock that behaves like a docker Container object."""
    container = MagicMock()
    container.id = "mock-container-id"
    container.wait.return_value = {"StatusCode": exit_code}

    def _logs(*, stdout=True, stderr=True):  # noqa: FBT002
        if stdout and not stderr:
            return stdout_bytes
        if stderr and not stdout:
            return stderr_bytes
        return stdout_bytes + stderr_bytes

    stdout_bytes = stdout
    stderr_bytes = stderr
    container.logs = MagicMock(side_effect=_logs)
    return container


def _make_mock_client(container):
    """Return a MagicMock Docker client whose containers.create returns *container*."""
    client = MagicMock()
    client.containers.create.return_value = container
    return client


_SETTINGS_PATCH = "app.services.docker_runner.settings"
_CLIENT_PATCH = "app.services.docker_runner._get_client"


class TestRunContainerSync(unittest.TestCase):
    """Tests for _run_container_sync (the synchronous core)."""

    @patch(_CLIENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_successful_run(self, mock_settings, mock_get_client):
        mock_settings.DOCKER_CONTAINER_TIMEOUT = 60
        container = _make_mock_container(exit_code=0, stdout=b"hello\n", stderr=b"")
        client = _make_mock_client(container)
        mock_get_client.return_value = client

        config = ContainerConfig(image="python:3.12-slim", command="echo hello")
        result = _run_container_sync(config)

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "hello\n")
        self.assertEqual(result.stderr, "")
        self.assertFalse(result.timed_out)
        container.start.assert_called_once()
        container.remove.assert_called_once_with(force=True)
        client.close.assert_called_once()

    @patch(_CLIENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_nonzero_exit_code(self, mock_settings, mock_get_client):
        mock_settings.DOCKER_CONTAINER_TIMEOUT = 60
        container = _make_mock_container(exit_code=1, stdout=b"", stderr=b"fail\n")
        client = _make_mock_client(container)
        mock_get_client.return_value = client

        config = ContainerConfig(image="python:3.12-slim", command="false")
        result = _run_container_sync(config)

        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stderr, "fail\n")
        self.assertFalse(result.timed_out)

    @patch(_CLIENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_container_removed_on_wait_timeout(self, mock_settings, mock_get_client):
        """When container.wait() raises (e.g. timeout), container is killed and removed."""
        mock_settings.DOCKER_CONTAINER_TIMEOUT = 60
        container = _make_mock_container(stdout=b"partial\n", stderr=b"")
        container.wait.side_effect = ConnectionError("timed out")
        client = _make_mock_client(container)
        mock_get_client.return_value = client

        config = ContainerConfig(image="python:3.12-slim", command="sleep 999")
        result = _run_container_sync(config)

        self.assertTrue(result.timed_out)
        self.assertEqual(result.exit_code, -1)
        container.kill.assert_called_once()
        container.remove.assert_called_once_with(force=True)
        client.close.assert_called_once()

    @patch(_CLIENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_docker_runner_error_when_kill_fails(self, mock_settings, mock_get_client):
        """When both wait and kill fail, DockerRunnerError is raised."""
        mock_settings.DOCKER_CONTAINER_TIMEOUT = 60
        container = _make_mock_container()
        container.wait.side_effect = ConnectionError("timed out")
        container.kill.side_effect = Exception("kill failed")
        client = _make_mock_client(container)
        mock_get_client.return_value = client

        config = ContainerConfig(image="python:3.12-slim", command="sleep 999")
        with self.assertRaises(DockerRunnerError):
            _run_container_sync(config)

        container.remove.assert_called_once_with(force=True)

    @patch(_CLIENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_volumes_and_env_passed_through(self, mock_settings, mock_get_client):
        mock_settings.DOCKER_CONTAINER_TIMEOUT = 60
        container = _make_mock_container()
        client = _make_mock_client(container)
        mock_get_client.return_value = client

        volumes = {"/host/path": {"bind": "/container/path", "mode": "ro"}}
        env = {"MY_VAR": "value"}
        config = ContainerConfig(
            image="python:3.12-slim",
            command="echo ok",
            volumes=volumes,
            environment=env,
            working_dir="/app",
        )
        _run_container_sync(config)

        create_call = client.containers.create.call_args
        self.assertEqual(create_call.kwargs.get("volumes") or create_call[1].get("volumes"), volumes)
        self.assertEqual(create_call.kwargs.get("environment") or create_call[1].get("environment"), env)
        self.assertEqual(create_call.kwargs.get("working_dir") or create_call[1].get("working_dir"), "/app")

    @patch(_CLIENT_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_config_timeout_overrides_default(self, mock_settings, mock_get_client):
        mock_settings.DOCKER_CONTAINER_TIMEOUT = 60
        container = _make_mock_container()
        client = _make_mock_client(container)
        mock_get_client.return_value = client

        config = ContainerConfig(image="python:3.12-slim", command="echo ok", timeout=10)
        _run_container_sync(config)

        container.wait.assert_called_once_with(timeout=10)


class TestRunContainerAsync(unittest.IsolatedAsyncioTestCase):
    """Tests for the async run_container wrapper."""

    @patch("app.services.docker_runner._run_container_sync")
    async def test_async_delegates_to_sync(self, mock_sync):
        from app.services.docker_runner import run_container

        expected = ContainerResult(exit_code=0, stdout="ok", stderr="")
        mock_sync.return_value = expected

        config = ContainerConfig(image="python:3.12-slim", command="echo ok")
        result = await run_container(config)

        mock_sync.assert_called_once_with(config)
        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
