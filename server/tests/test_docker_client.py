"""Unit tests for the docker_client bridge module."""

import unittest
from unittest.mock import AsyncMock, patch

from app.services.docker_client import ContainerResult, _build_shell_command, run_container
from app.services.docker_runner import ContainerConfig
from app.services.docker_runner import ContainerResult as RunnerResult
from app.services.sandbox_images import SANDBOX_PROFILES, get_sandbox_profile


class TestBuildShellCommand(unittest.TestCase):
    def test_python_command_includes_conditional_install(self) -> None:
        profile = SANDBOX_PROFILES["python"]
        cmd = _build_shell_command(profile)
        self.assertEqual(cmd[0], "sh")
        self.assertEqual(cmd[1], "-c")
        self.assertIn("pytest", cmd[2])
        self.assertIn("test -f requirements.txt", cmd[2])

    def test_java_command_has_no_install(self) -> None:
        profile = SANDBOX_PROFILES["java"]
        cmd = _build_shell_command(profile)
        self.assertIn("mvn test", cmd[2])
        self.assertNotIn("install", cmd[2])

    def test_javascript_command_includes_conditional_install(self) -> None:
        profile = SANDBOX_PROFILES["javascript"]
        cmd = _build_shell_command(profile)
        self.assertIn("test -f package.json", cmd[2])
        self.assertIn("npm ci", cmd[2])
        self.assertIn("jest", cmd[2])

    def test_typescript_command_includes_conditional_install(self) -> None:
        profile = SANDBOX_PROFILES["typescript"]
        cmd = _build_shell_command(profile)
        self.assertIn("test -f package.json", cmd[2])
        self.assertIn("jest", cmd[2])

    def test_all_commands_start_with_cd_workspace(self) -> None:
        for lang, profile in SANDBOX_PROFILES.items():
            with self.subTest(lang=lang):
                cmd = _build_shell_command(profile)
                self.assertTrue(cmd[2].startswith("cd /workspace/tests"))


class TestRunContainer(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_python_builds_correct_config(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="ok", stderr="", timed_out=False,
        )
        result = await run_container("python", "/host/student", "/host/tests", timeout_seconds=30)

        mock_run.assert_awaited_once()
        config: ContainerConfig = mock_run.await_args[0][0]
        self.assertEqual(config.image, "python:3.12-slim")
        self.assertIn("/host/student", config.volumes)
        self.assertIn("/host/tests", config.volumes)
        self.assertEqual(config.volumes["/host/student"]["mode"], "ro")
        self.assertEqual(config.volumes["/host/tests"]["mode"], "ro")
        self.assertEqual(config.timeout, 30)
        self.assertEqual(config.working_dir, "/workspace")

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_java_uses_maven_image(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )
        await run_container("java", "/s", "/t")
        config: ContainerConfig = mock_run.await_args[0][0]
        self.assertIn("maven", config.image)

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_javascript_uses_node_image(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )
        await run_container("javascript", "/s", "/t")
        config: ContainerConfig = mock_run.await_args[0][0]
        self.assertIn("node", config.image)

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_unknown_language_falls_back_to_python(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )
        await run_container("rust", "/s", "/t")
        config: ContainerConfig = mock_run.await_args[0][0]
        self.assertEqual(config.image, "python:3.12-slim")

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_result_conversion(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=1, stdout="out", stderr="err", timed_out=True,
        )
        result = await run_container("python", "/s", "/t")

        self.assertIsInstance(result, ContainerResult)
        self.assertEqual(result.exit_code, 1)
        self.assertEqual(result.stdout, "out")
        self.assertEqual(result.stderr, "err")
        # timed_out is NOT exposed in the public ContainerResult
        self.assertFalse(hasattr(result, "timed_out"))


if __name__ == "__main__":
    unittest.main()
