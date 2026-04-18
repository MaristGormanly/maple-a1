"""Unit tests for the LLM service (server/app/services/llm.py).

Covers retry/fallback logic, redaction of PII before dispatch,
timeout handling, and complexity-based timeout selection.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.llm import (
    EvaluationFailedError,
    LLMResponse,
    LLMUsage,
    ModelSpec,
    ProviderError,
    complete,
    redact,
)


_FAKE_USAGE = LLMUsage(input_tokens=100, output_tokens=50, cost_usd=0.001)
_FAKE_RESPONSE = LLMResponse(content="evaluation result", usage=_FAKE_USAGE, latency_ms=123)

_SETTINGS_PATCH = "app.services.llm.settings"
_DISPATCH_PATCH = "app.services.llm._dispatch"
_SLEEP_PATCH = "app.services.llm.asyncio.sleep"
_WAIT_FOR_PATCH = "app.services.llm.asyncio.wait_for"


def _make_settings(*, max_retries=2, backoff_base=1.0, timeout_standard=30, timeout_complex=60):
    s = MagicMock()
    s.LLM_MAX_RETRIES = max_retries
    s.LLM_BACKOFF_BASE = backoff_base
    s.LLM_TIMEOUT_STANDARD = timeout_standard
    s.LLM_TIMEOUT_COMPLEX = timeout_complex
    return s


class TestCompleteSuccessFirstAttempt(unittest.IsolatedAsyncioTestCase):
    """complete() returns immediately without sleeping on a clean first-attempt success."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_DISPATCH_PATCH, return_value=_FAKE_RESPONSE)
    @patch(_SETTINGS_PATCH)
    async def test_complete_success_first_attempt(self, mock_settings, mock_dispatch, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        result = await complete("system prompt", [{"role": "user", "content": "hello"}])

        self.assertEqual(result.content, _FAKE_RESPONSE.content)
        self.assertEqual(result.usage, _FAKE_RESPONSE.usage)
        self.assertIsInstance(result.latency_ms, int)
        mock_sleep.assert_not_called()


class TestCompleteRetriesThenSucceeds(unittest.IsolatedAsyncioTestCase):
    """complete() retries once on ProviderError then succeeds, sleeping with backoff."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_complete_retries_then_succeeds(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        call_count = 0

        def dispatch_side_effect(spec, system, messages, max_tokens, temperature):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("transient failure")
            return _FAKE_RESPONSE

        with patch(_DISPATCH_PATCH, side_effect=dispatch_side_effect):
            result = await complete("system prompt", [{"role": "user", "content": "hello"}])

        self.assertEqual(result.content, _FAKE_RESPONSE.content)
        # backoff_base * 2^0 = 1.0 * 1 = 1.0
        mock_sleep.assert_called_once_with(1.0)


class TestCompleteAllRetriesSameModelFallsThrough(unittest.IsolatedAsyncioTestCase):
    """First model exhausts all retries; second model succeeds (fallback path)."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_complete_retries_both_attempts_same_model_falls_through(
        self, mock_settings, mock_sleep
    ):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        first_model_name = "gemini-3.1-pro-preview"

        def dispatch_side_effect(spec, system, messages, max_tokens, temperature):
            if spec.name == first_model_name:
                raise ProviderError("first model always fails")
            return _FAKE_RESPONSE

        with patch(_DISPATCH_PATCH, side_effect=dispatch_side_effect):
            result = await complete("system prompt", [{"role": "user", "content": "hello"}])

        self.assertEqual(result.content, _FAKE_RESPONSE.content)
        # First model used 2 retries; sleep should have been called for retry on first attempt.
        self.assertTrue(mock_sleep.called)


class TestCompleteAllModelsExhaustedRaises(unittest.IsolatedAsyncioTestCase):
    """EvaluationFailedError raised when every model in MODEL_CHAIN fails all retries."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_DISPATCH_PATCH, side_effect=ProviderError("always fail"))
    @patch(_SETTINGS_PATCH)
    async def test_complete_all_models_exhausted_raises(
        self, mock_settings, mock_dispatch, mock_sleep
    ):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        with self.assertRaises(EvaluationFailedError):
            await complete("system prompt", [{"role": "user", "content": "hello"}])


class TestCompleteTimeoutRespected(unittest.IsolatedAsyncioTestCase):
    """asyncio.TimeoutError from wait_for triggers retry/fallback then exhaustion."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_complete_timeout_respected(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        async def fake_wait_for(coro, timeout):
            coro.close()  # prevent ResourceWarning: coroutine never awaited
            raise asyncio.TimeoutError("timed out")

        with patch(_WAIT_FOR_PATCH, side_effect=fake_wait_for):
            with self.assertRaises(EvaluationFailedError):
                await complete("system prompt", [{"role": "user", "content": "hello"}])

        self.assertTrue(mock_sleep.called)


class TestCompleteRedactsSystemPrompt(unittest.IsolatedAsyncioTestCase):
    """GitHub PAT in system_prompt must be stripped before reaching _dispatch."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_complete_redacts_system_prompt(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        fake_pat = "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        captured_system = []

        def dispatch_capture(spec, system, messages, max_tokens, temperature):
            captured_system.append(system)
            return _FAKE_RESPONSE

        with patch(_DISPATCH_PATCH, side_effect=dispatch_capture):
            await complete(
                f"Use token {fake_pat} to auth",
                [{"role": "user", "content": "evaluate"}],
            )

        self.assertTrue(captured_system, "dispatch should have been called")
        self.assertNotIn(fake_pat, captured_system[0])
        self.assertIn("[REDACTED_GITHUB_PAT]", captured_system[0])


class TestCompleteRedactsMessages(unittest.IsolatedAsyncioTestCase):
    """Email addresses in message content must be redacted before reaching _dispatch."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_complete_redacts_messages(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        email_addr = "student@university.edu"
        captured_messages = []

        def dispatch_capture(spec, system, messages, max_tokens, temperature):
            captured_messages.extend(messages)
            return _FAKE_RESPONSE

        with patch(_DISPATCH_PATCH, side_effect=dispatch_capture):
            await complete(
                "system prompt",
                [{"role": "user", "content": f"My email is {email_addr}"}],
            )

        self.assertTrue(captured_messages, "dispatch should have been called")
        for msg in captured_messages:
            self.assertNotIn(email_addr, msg.get("content", ""))


class TestCompleteComplexityTimeouts(unittest.IsolatedAsyncioTestCase):
    """complexity='standard' uses LLM_TIMEOUT_STANDARD; 'complex' uses LLM_TIMEOUT_COMPLEX."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_complete_complexity_standard(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        captured_timeout = []

        async def fake_wait_for(coro, timeout):
            captured_timeout.append(timeout)
            # Discard the coroutine to avoid ResourceWarning.
            coro.close()
            return _FAKE_RESPONSE

        with patch(_WAIT_FOR_PATCH, side_effect=fake_wait_for):
            result = await complete(
                "system", [{"role": "user", "content": "hi"}], complexity="standard"
            )

        self.assertTrue(captured_timeout)
        self.assertEqual(captured_timeout[0], 30)

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_complete_complexity_complex(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        captured_timeout = []

        async def fake_wait_for(coro, timeout):
            captured_timeout.append(timeout)
            coro.close()
            return _FAKE_RESPONSE

        with patch(_WAIT_FOR_PATCH, side_effect=fake_wait_for):
            result = await complete(
                "system", [{"role": "user", "content": "hi"}], complexity="complex"
            )

        self.assertTrue(captured_timeout)
        self.assertEqual(captured_timeout[0], 60)


if __name__ == "__main__":
    unittest.main()
