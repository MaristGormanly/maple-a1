"""Unit tests for the sandbox_images module."""

import unittest

from app.services.sandbox_images import (
    DEFAULT_PROFILE,
    SANDBOX_PROFILES,
    SandboxProfile,
    get_sandbox_profile,
)


class TestSandboxProfiles(unittest.TestCase):
    def test_python_profile(self) -> None:
        p = SANDBOX_PROFILES["python"]
        self.assertEqual(p.language, "python")
        self.assertEqual(p.image, "python:3.12-slim")
        self.assertIn("pytest", p.test_command)

    def test_java_profile(self) -> None:
        p = SANDBOX_PROFILES["java"]
        self.assertEqual(p.language, "java")
        self.assertIn("maven", p.image)
        self.assertIn("mvn test", p.test_command)
        self.assertIn("maple_status=$?", p.test_command)
        self.assertTrue(p.test_command.endswith("exit $maple_status"))
        self.assertIsNone(p.install_command)

    def test_javascript_profile(self) -> None:
        p = SANDBOX_PROFILES["javascript"]
        self.assertEqual(p.language, "javascript")
        self.assertIn("node", p.image)
        self.assertIn("jest", p.test_command)

    def test_typescript_profile(self) -> None:
        p = SANDBOX_PROFILES["typescript"]
        self.assertEqual(p.language, "typescript")
        self.assertIn("node", p.image)
        self.assertIn("jest", p.test_command)

    def test_js_and_ts_share_node_image(self) -> None:
        self.assertEqual(
            SANDBOX_PROFILES["javascript"].image,
            SANDBOX_PROFILES["typescript"].image,
        )

    def test_all_profiles_have_image_and_test_command(self) -> None:
        for lang, profile in SANDBOX_PROFILES.items():
            with self.subTest(lang=lang):
                self.assertTrue(profile.image, f"{lang} missing image")
                self.assertTrue(profile.test_command, f"{lang} missing test_command")

    def test_all_profiles_have_working_dir(self) -> None:
        for lang, profile in SANDBOX_PROFILES.items():
            with self.subTest(lang=lang):
                self.assertTrue(profile.working_dir)

    def test_profiles_are_frozen(self) -> None:
        p = SANDBOX_PROFILES["python"]
        with self.assertRaises(AttributeError):
            p.image = "other:image"  # type: ignore[misc]


class TestGetSandboxProfile(unittest.TestCase):
    def test_returns_python(self) -> None:
        profile, version_ok = get_sandbox_profile("python")
        self.assertEqual(profile.language, "python")
        self.assertTrue(version_ok)

    def test_returns_java(self) -> None:
        profile, version_ok = get_sandbox_profile("java")
        self.assertEqual(profile.language, "java")
        self.assertTrue(version_ok)

    def test_returns_javascript(self) -> None:
        profile, version_ok = get_sandbox_profile("javascript")
        self.assertEqual(profile.language, "javascript")
        self.assertTrue(version_ok)

    def test_returns_typescript(self) -> None:
        profile, version_ok = get_sandbox_profile("typescript")
        self.assertEqual(profile.language, "typescript")
        self.assertTrue(version_ok)

    def test_unknown_falls_back_to_default(self) -> None:
        profile, version_ok = get_sandbox_profile("rust")
        self.assertEqual(profile, DEFAULT_PROFILE)
        self.assertTrue(version_ok)

    def test_empty_string_falls_back(self) -> None:
        profile, version_ok = get_sandbox_profile("")
        self.assertEqual(profile, DEFAULT_PROFILE)
        self.assertTrue(version_ok)

    def test_none_falls_back(self) -> None:
        profile, version_ok = get_sandbox_profile(None)  # type: ignore[arg-type]
        self.assertEqual(profile, DEFAULT_PROFILE)
        self.assertTrue(version_ok)

    def test_case_insensitive(self) -> None:
        python_profile, _ = get_sandbox_profile("Python")
        java_profile, _ = get_sandbox_profile("JAVA")
        js_profile, _ = get_sandbox_profile("JavaScript")
        self.assertEqual(python_profile.language, "python")
        self.assertEqual(java_profile.language, "java")
        self.assertEqual(js_profile.language, "javascript")

    def test_default_profile_is_python(self) -> None:
        self.assertEqual(DEFAULT_PROFILE.language, "python")


if __name__ == "__main__":
    unittest.main()
