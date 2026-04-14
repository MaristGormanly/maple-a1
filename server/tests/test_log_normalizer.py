"""Unit tests for the log_normalizer module.

Covers the truncation contract defined in design-doc §3 §IV:
  - retain first 2 KB (HEAD_BYTES) and last 5 KB (TAIL_BYTES)
  - discard the middle
  - human-readable separator at the cut point
"""

import unittest

from app.services.log_normalizer import HEAD_BYTES, TAIL_BYTES, normalize_logs

_LIMIT = HEAD_BYTES + TAIL_BYTES  # 7 168 bytes


def _make_text(size_bytes: int, char: str = "A") -> str:
    """Return an ASCII string whose UTF-8 encoding is exactly *size_bytes* bytes."""
    return char * size_bytes


class TestNormalizeLogsNoTruncation(unittest.TestCase):
    """Texts at or below the limit must pass through unchanged."""

    def test_empty_string(self) -> None:
        self.assertEqual(normalize_logs(""), "")

    def test_single_char(self) -> None:
        self.assertEqual(normalize_logs("x"), "x")

    def test_short_text_unchanged(self) -> None:
        text = "hello\n" * 10
        self.assertEqual(normalize_logs(text), text)

    def test_exactly_at_limit_unchanged(self) -> None:
        text = _make_text(_LIMIT)
        self.assertEqual(normalize_logs(text), text)

    def test_one_byte_under_limit_unchanged(self) -> None:
        text = _make_text(_LIMIT - 1)
        self.assertEqual(normalize_logs(text), text)


class TestNormalizeLogsTruncation(unittest.TestCase):
    """Texts over the limit must be truncated with the correct head and tail."""

    def _over_limit_text(self) -> str:
        """Build a text that is 1 byte over the limit."""
        return _make_text(_LIMIT + 1)

    def test_one_byte_over_limit_is_truncated(self) -> None:
        # One byte over the limit — the 1 middle byte is replaced by the separator.
        # The separator itself adds more bytes than the 1 discarded byte, so we
        # cannot assert the output is *smaller*; instead assert content was cut.
        text = self._over_limit_text()
        result = normalize_logs(text)
        self.assertIn("[1 bytes omitted]", result)

    def test_separator_present_on_truncation(self) -> None:
        text = _make_text(_LIMIT + 100)
        result = normalize_logs(text)
        self.assertIn("bytes omitted", result)

    def test_head_preserved(self) -> None:
        # Mark the head with distinctive characters.
        head = "H" * HEAD_BYTES
        body = "M" * 1000
        tail = "T" * TAIL_BYTES
        text = head + body + tail
        result = normalize_logs(text)
        # The result must start with the first HEAD_BYTES worth of head content.
        self.assertTrue(result.startswith("H" * HEAD_BYTES))

    def test_tail_preserved(self) -> None:
        head = "H" * HEAD_BYTES
        body = "M" * 1000
        tail = "T" * TAIL_BYTES
        text = head + body + tail
        result = normalize_logs(text)
        # The result must end with the last TAIL_BYTES worth of tail content.
        self.assertTrue(result.endswith("T" * TAIL_BYTES))

    def test_middle_discarded(self) -> None:
        head = "H" * HEAD_BYTES
        body = "MIDDLE_CONTENT"
        tail = "T" * TAIL_BYTES
        text = head + body + tail
        result = normalize_logs(text)
        self.assertNotIn("MIDDLE_CONTENT", result)

    def test_omitted_byte_count_correct(self) -> None:
        extra = 500
        text = _make_text(_LIMIT + extra)
        result = normalize_logs(text)
        self.assertIn(f"[{extra} bytes omitted]", result)

    def test_large_log_truncated_correctly(self) -> None:
        # Simulate a 1 MB log — well beyond the limit.
        text = _make_text(1024 * 1024)
        result = normalize_logs(text)
        encoded = result.encode("utf-8")
        # Output must be larger than limit (separator adds a few bytes) but
        # must NOT exceed limit + a generous separator allowance (100 bytes).
        self.assertGreater(len(encoded), _LIMIT)
        self.assertLess(len(encoded), _LIMIT + 100)


class TestNormalizeLogsMultibyte(unittest.TestCase):
    """UTF-8 multi-byte characters must not cause decode errors at cut points."""

    def test_multibyte_chars_no_exception(self) -> None:
        # Each '€' is 3 UTF-8 bytes; build a string that is slightly over the
        # limit so the cut point may fall inside a multi-byte sequence.
        char = "€"  # 3 bytes
        # Ensure the total byte length is just over _LIMIT so truncation fires.
        count = (_LIMIT // 3) + 10
        text = char * count
        # Should not raise; errors="replace" handles partial sequences.
        result = normalize_logs(text)
        self.assertIsInstance(result, str)

    def test_multibyte_result_is_valid_str(self) -> None:
        char = "\U0001F600"  # 4-byte emoji
        count = (_LIMIT // 4) + 10
        text = char * count
        result = normalize_logs(text)
        # Round-trip: must encode back to UTF-8 without error.
        result.encode("utf-8")


class TestNormalizeLogsIntegration(unittest.TestCase):
    """Verify that normalize_logs is wired into docker_client.run_container."""

    def test_normalize_logs_called_on_stdout_and_stderr(self) -> None:
        """run_container must apply normalize_logs to both stdout and stderr."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        from app.services.docker_client import run_container
        from app.services.docker_runner import ContainerResult as RunnerResult

        oversized = "X" * (_LIMIT + 500)
        runner_result = RunnerResult(
            exit_code=0, stdout=oversized, stderr=oversized, timed_out=False
        )

        with patch("app.services.docker_client._docker_run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = runner_result
            result = asyncio.run(
                run_container("python", "/student", "/tests", timeout_seconds=30)
            )

        # Both fields must be shorter than the raw oversized string.
        self.assertLess(len(result.stdout.encode("utf-8")), len(oversized.encode("utf-8")))
        self.assertLess(len(result.stderr.encode("utf-8")), len(oversized.encode("utf-8")))
        self.assertIn("bytes omitted", result.stdout)
        self.assertIn("bytes omitted", result.stderr)

    def test_short_logs_pass_through_unchanged_via_client(self) -> None:
        """Short logs must not be altered by the bridge layer."""
        import asyncio
        from unittest.mock import AsyncMock, patch

        from app.services.docker_client import run_container
        from app.services.docker_runner import ContainerResult as RunnerResult

        runner_result = RunnerResult(
            exit_code=0, stdout="short stdout", stderr="short stderr", timed_out=False
        )

        with patch("app.services.docker_client._docker_run", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = runner_result
            result = asyncio.run(
                run_container("python", "/student", "/tests", timeout_seconds=30)
            )

        self.assertEqual(result.stdout, "short stdout")
        self.assertEqual(result.stderr, "short stderr")


if __name__ == "__main__":
    unittest.main()
