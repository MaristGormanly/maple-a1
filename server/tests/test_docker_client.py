"""Unit tests for the docker_client bridge module."""

import unittest
from unittest.mock import AsyncMock, patch

from app.services.docker_client import (
    ContainerResult,
    _build_shell_command,
    _cpp_auto_discover_command,
    _install_prelude,
    run_container,
)
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
        self.assertIn("maple_status=$?", cmd[2])
        self.assertTrue(cmd[2].endswith("exit $maple_status"))

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
        self.assertFalse(config.network_disabled)

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

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_preserves_test_command_exit_code(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=1, stdout="", stderr="build failed", timed_out=False,
        )

        await run_container(
            "java",
            "/host/student",
            None,
            discovered_command="mvn test",
            discovered_working_dir=".",
        )

        config: ContainerConfig = mock_run.await_args[0][0]
        command = config.command[2]
        self.assertIn("mvn test", command)
        self.assertIn("maple_status=$?", command)
        self.assertTrue(command.endswith("exit $maple_status"))

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_merges_stderr_into_stdout(self, mock_run) -> None:
        # exec 2>&1 at the start of the script ensures Maven's stderr output
        # (build logs, test summaries) lands in the stdout buffer captured by
        # log_normalizer, so the test parser sees the full [INFO] summary tail.
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )

        await run_container(
            "java",
            "/host/student",
            None,
            discovered_command="mvn test",
            discovered_working_dir=".",
        )

        command = mock_run.await_args[0][0].command[2]
        self.assertTrue(command.startswith("exec 2>&1"), "stderr must be merged before cp")

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_cpp_uses_profile_test_command(self, mock_run) -> None:
        # The test_discoverer sanitizer blocks && so C++ auto-discover builds
        # first, then resolves the named test executable under build/.
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )

        await run_container(
            "cpp",
            "/host/student",
            None,
            discovered_command="./test/etl_tests -v",
            discovered_working_dir=".",
        )

        command = mock_run.await_args[0][0].command[2]
        self.assertIn("cmake", command)
        self.assertIn("-DBUILD_TESTS=ON", command)
        self.assertIn("-DBUILD_TESTING=ON", command)
        self.assertIn("find build -type f -name etl_tests", command)
        self.assertIn('"$cpp_candidate" -v', command)
        self.assertIn("ctest --output-on-failure --verbose", command)

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_cpp_keeps_read_only_root_fs(self, mock_run) -> None:
        # C++ dependencies are baked into maple-cpp-sandbox, so submitted-code
        # containers keep the read-only root filesystem and cap_drop=ALL.
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )

        await run_container(
            "cpp",
            "/host/student",
            None,
            discovered_command="./test/etl_tests -v",
            discovered_working_dir=".",
        )

        config: ContainerConfig = mock_run.await_args[0][0]
        self.assertEqual(config.image, "maple-cpp-sandbox:22.04")
        self.assertTrue(config.read_only)
        self.assertEqual(config.cap_drop, ["ALL"])

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_non_cpp_languages_keep_read_only_fs(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )
        for lang in ("python", "java", "javascript"):
            with self.subTest(lang=lang):
                await run_container(lang, "/s", "/t")
                config: ContainerConfig = mock_run.await_args[0][0]
                self.assertTrue(config.read_only, f"{lang} must use read-only FS")

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_does_not_cat_surefire_xml(self, mock_run) -> None:
        # Catting 741 surefire XML files (~2 MB) pushes Maven's [INFO] summary
        # into the log_normalizer dead-zone, resulting in tests=0.  The
        # surefire XML extraction was removed; Maven's text summary is now
        # the sole signal and always lands in the 5 KB tail window.
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )

        await run_container(
            "java",
            "/host/student",
            None,
            discovered_command="mvn test",
            discovered_working_dir=".",
        )

        command = mock_run.await_args[0][0].command[2]
        self.assertNotIn("surefire-reports", command)
        self.assertNotIn("find .", command)

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_python_installs_pytest(self, mock_run) -> None:
        # Regression: prod slim images ship without pytest; auto-discover must
        # install it before running the discovered command, otherwise the
        # container exits 1 instantly and the AI pipeline sees tests=0.
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )

        await run_container(
            "python",
            "/host/student",
            None,
            discovered_command="python -m pytest",
            discovered_working_dir=".",
        )

        command = mock_run.await_args[0][0].command[2]
        self.assertIn("pip install --no-cache-dir pytest", command)
        self.assertLess(
            command.index("pip install"),
            command.index("python -m pytest"),
            "install prelude must run before the discovered command",
        )

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_node_runs_npm_ci(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )

        await run_container(
            "javascript",
            "/host/student",
            None,
            discovered_command="npx jest",
            discovered_working_dir=".",
        )

        command = mock_run.await_args[0][0].command[2]
        self.assertIn("npm ci --ignore-scripts", command)

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_uses_cp_R_not_cp_a(self, mock_run) -> None:
        # Regression: `cp -a` preserves ownership, which needs CAP_CHOWN. The
        # sandbox runs with cap_drop=ALL, so on Linux hosts whose bind-mount
        # sources are owned by a non-root user (prod: UID 1000 maple), `cp -a`
        # short-circuits the whole && chain and the container exits 1 in <1s.
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )

        await run_container(
            "python",
            "/host/student",
            None,
            discovered_command="python -m pytest",
            discovered_working_dir=".",
        )

        command = mock_run.await_args[0][0].command[2]
        self.assertIn("cp -R /workspace/source/.", command)
        self.assertNotIn("cp -a ", command)

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_auto_discover_java_has_no_prelude(self, mock_run) -> None:
        # Maven images ship with `mvn`, no install step needed.
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )

        await run_container(
            "java",
            "/host/student",
            None,
            discovered_command="mvn test",
            discovered_working_dir=".",
        )

        command = mock_run.await_args[0][0].command[2]
        self.assertNotIn("pip install", command)
        self.assertNotIn("npm ci", command)


class TestProfileResourceBudgetFlowsThrough(unittest.IsolatedAsyncioTestCase):
    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_java_uses_wider_budget(self, mock_run) -> None:
        # Regression: Java/Maven needs minutes to download deps + compile, so
        # the profile's 600s / 2g / 1 CPU must reach ContainerConfig.
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )
        await run_container("java", "/s", "/t")
        config: ContainerConfig = mock_run.await_args[0][0]
        self.assertEqual(config.timeout, 600)
        self.assertEqual(config.mem_limit, "2g")
        self.assertEqual(config.cpu_quota, 100_000)

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_python_keeps_default_budget(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )
        await run_container("python", "/s", "/t")
        config: ContainerConfig = mock_run.await_args[0][0]
        self.assertEqual(config.timeout, 120)
        self.assertEqual(config.mem_limit, "256m")
        self.assertEqual(config.cpu_quota, 50_000)

    @patch("app.services.docker_client._docker_run", new_callable=AsyncMock)
    async def test_explicit_timeout_overrides_profile_default(self, mock_run) -> None:
        mock_run.return_value = RunnerResult(
            exit_code=0, stdout="", stderr="", timed_out=False,
        )
        await run_container("java", "/s", "/t", timeout_seconds=42)
        config: ContainerConfig = mock_run.await_args[0][0]
        self.assertEqual(config.timeout, 42)


class TestInstallPrelude(unittest.TestCase):
    def test_python_prelude_installs_pytest_then_requirements(self) -> None:
        prelude = _install_prelude(SANDBOX_PROFILES["python"])
        self.assertIsNotNone(prelude)
        self.assertIn("pip install --no-cache-dir pytest", prelude)
        self.assertIn("requirements.txt", prelude)

    def test_java_prelude_is_none(self) -> None:
        self.assertIsNone(_install_prelude(SANDBOX_PROFILES["java"]))

    def test_javascript_prelude_uses_npm_ci(self) -> None:
        prelude = _install_prelude(SANDBOX_PROFILES["javascript"])
        self.assertIsNotNone(prelude)
        self.assertIn("npm ci --ignore-scripts", prelude)

    def test_cpp_prelude_is_none(self) -> None:
        self.assertIsNone(_install_prelude(SANDBOX_PROFILES["cpp"]))


class TestCppAutoDiscoverCommand(unittest.TestCase):
    def test_enables_cmake_tests_and_preserves_discovered_args(self) -> None:
        command = _cpp_auto_discover_command("./test/etl_tests -v")
        self.assertIn("-DBUILD_TESTS=ON", command)
        self.assertIn("-DBUILD_TESTING=ON", command)
        self.assertIn("cmake --build build --parallel 2", command)
        self.assertIn("find build -type f -name etl_tests", command)
        self.assertIn('"$cpp_candidate" -v', command)
        self.assertIn("ctest --output-on-failure --verbose", command)


if __name__ == "__main__":
    unittest.main()
