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
        self.assertEqual(get_sandbox_profile("python").language, "python")

    def test_returns_java(self) -> None:
        self.assertEqual(get_sandbox_profile("java").language, "java")

    def test_returns_javascript(self) -> None:
        self.assertEqual(get_sandbox_profile("javascript").language, "javascript")

    def test_returns_typescript(self) -> None:
        self.assertEqual(get_sandbox_profile("typescript").language, "typescript")

    def test_unknown_falls_back_to_default(self) -> None:
        self.assertEqual(get_sandbox_profile("rust"), DEFAULT_PROFILE)

    def test_empty_string_falls_back(self) -> None:
        self.assertEqual(get_sandbox_profile(""), DEFAULT_PROFILE)

    def test_none_falls_back(self) -> None:
        self.assertEqual(get_sandbox_profile(None), DEFAULT_PROFILE)  # type: ignore[arg-type]

    def test_case_insensitive(self) -> None:
        self.assertEqual(get_sandbox_profile("Python").language, "python")
        self.assertEqual(get_sandbox_profile("JAVA").language, "java")
        self.assertEqual(get_sandbox_profile("JavaScript").language, "javascript")

    def test_default_profile_is_python(self) -> None:
        self.assertEqual(DEFAULT_PROFILE.language, "python")


if __name__ == "__main__":
    unittest.main()
