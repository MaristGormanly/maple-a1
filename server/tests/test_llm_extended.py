"""Extended unit tests for app.services.llm — structured logging, backoff timing,
redactor edge cases, and response field population.
"""

import asyncio
import json
import logging
import unittest
from unittest.mock import AsyncMock, MagicMock, patch, call

from app.services.llm import (
    EvaluationFailedError,
    LLMResponse,
    LLMUsage,
    MODEL_CHAIN,
    ModelSpec,
    ProviderError,
    complete,
    redact,
    redact_dict,
)

_SETTINGS_PATCH = "app.services.llm.settings"
_DISPATCH_PATCH = "app.services.llm._dispatch"
_SLEEP_PATCH = "app.services.llm.asyncio.sleep"
_WAIT_FOR_PATCH = "app.services.llm.asyncio.wait_for"

_FAKE_USAGE = LLMUsage(input_tokens=80, output_tokens=40, cost_usd=0.002)
_FAKE_RESPONSE = LLMResponse(content="ok", usage=_FAKE_USAGE, latency_ms=0)


def _make_settings(max_retries=2, backoff_base=1.0, timeout_std=30, timeout_cplx=60):
    s = MagicMock()
    s.LLM_MAX_RETRIES = max_retries
    s.LLM_BACKOFF_BASE = backoff_base
    s.LLM_TIMEOUT_STANDARD = timeout_std
    s.LLM_TIMEOUT_COMPLEX = timeout_cplx
    return s


# ---------------------------------------------------------------------------
# Redactor unit tests
# ---------------------------------------------------------------------------

class TestRedact(unittest.TestCase):
    def test_github_pat_redacted(self):
        text = "token=ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        result = redact(text)
        self.assertNotIn("ghp_", result)
        self.assertIn("[REDACTED_GITHUB_PAT]", result)

    def test_github_server_pat_redacted(self):
        text = "ghs_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        self.assertNotIn("ghs_", redact(text))

    def test_email_redacted(self):
        result = redact("Contact me at user@example.com please")
        self.assertNotIn("user@example.com", result)
        self.assertIn("[REDACTED_EMAIL]", result)

    def test_env_var_value_redacted(self):
        result = redact("DATABASE_URL=postgres://user:pass@host/db")
        self.assertNotIn("postgres://", result)
        self.assertIn("[REDACTED_ENV_VALUE]", result)

    def test_clean_text_unchanged(self):
        text = "Evaluate the student's implementation of quicksort."
        self.assertEqual(redact(text), text)

    def test_multiple_secrets_all_redacted(self):
        text = "pat=ghp_cccccccccccccccccccccccccccccccccccccc email=x@y.com"
        result = redact(text)
        self.assertNotIn("ghp_", result)
        self.assertNotIn("x@y.com", result)


class TestRedactDict(unittest.TestCase):
    def test_nested_email_redacted(self):
        data = {"user": {"email": "a@b.com", "name": "Alice"}, "note": "hello"}
        result = redact_dict(data)
        self.assertNotIn("a@b.com", result["user"]["email"])
        self.assertEqual(result["user"]["name"], "Alice")

    def test_original_not_mutated(self):
        data = {"content": "ghp_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
        redact_dict(data)
        self.assertIn("ghp_", data["content"])

    def test_list_of_strings_redacted(self):
        data = {"messages": ["hello user@domain.com", "safe text"]}
        result = redact_dict(data)
        self.assertNotIn("user@domain.com", result["messages"][0])
        self.assertEqual(result["messages"][1], "safe text")


# ---------------------------------------------------------------------------
# Backoff timing
# ---------------------------------------------------------------------------

class TestBackoffTiming(unittest.IsolatedAsyncioTestCase):
    """Backoff sleeps use backoff_base * 2^(attempt-1)."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_first_retry_sleeps_1s_with_base_1(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        call_count = 0
        def side_effect(spec, *a):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("fail once")
            return _FAKE_RESPONSE

        with patch(_DISPATCH_PATCH, side_effect=side_effect):
            await complete("s", [])

        mock_sleep.assert_called_once_with(1.0)

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_backoff_base_scales_sleep(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 0.5
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        call_count = 0
        def side_effect(spec, *a):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("fail")
            return _FAKE_RESPONSE

        with patch(_DISPATCH_PATCH, side_effect=side_effect):
            await complete("s", [])

        mock_sleep.assert_called_once_with(0.5)  # 0.5 * 2^0


# ---------------------------------------------------------------------------
# Structured log output
# ---------------------------------------------------------------------------

class TestStructuredLogging(unittest.IsolatedAsyncioTestCase):
    """complete() emits structured JSON logs with required fields."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_DISPATCH_PATCH)
    @patch(_SETTINGS_PATCH)
    async def test_success_log_has_required_fields(self, mock_settings, mock_dispatch, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60
        mock_dispatch.return_value = _FAKE_RESPONSE

        with self.assertLogs("app.services.llm", level="INFO") as log_ctx:
            await complete("system", [{"role": "user", "content": "q"}])

        info_records = [r for r in log_ctx.output if "INFO" in r]
        self.assertTrue(info_records, "Expected at least one INFO log")
        payload = json.loads(info_records[0].split("INFO:app.services.llm:")[-1])
        for field in ("event", "model", "attempt", "latency_ms", "input_tokens", "output_tokens", "status"):
            self.assertIn(field, payload, f"Missing field: {field}")
        self.assertEqual(payload["event"], "llm_call")
        self.assertEqual(payload["status"], "ok")

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_SETTINGS_PATCH)
    async def test_retry_log_has_required_fields(self, mock_settings, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        call_count = 0
        def side_effect(spec, *a):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderError("transient")
            return _FAKE_RESPONSE

        with self.assertLogs("app.services.llm", level="WARNING") as log_ctx:
            with patch(_DISPATCH_PATCH, side_effect=side_effect):
                await complete("s", [])

        warn_records = [r for r in log_ctx.output if "WARNING" in r]
        self.assertTrue(warn_records)
        payload = json.loads(warn_records[0].split("WARNING:app.services.llm:")[-1])
        for field in ("event", "model", "attempt", "latency_ms", "error_type", "status"):
            self.assertIn(field, payload, f"Missing field: {field}")
        self.assertEqual(payload["status"], "retry")

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_DISPATCH_PATCH, side_effect=ProviderError("always fail"))
    @patch(_SETTINGS_PATCH)
    async def test_model_exhausted_log_emitted(self, mock_settings, mock_dispatch, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60

        with self.assertLogs("app.services.llm", level="ERROR") as log_ctx:
            with self.assertRaises(EvaluationFailedError):
                await complete("s", [])

        error_records = [r for r in log_ctx.output if "ERROR" in r]
        self.assertTrue(error_records)
        payload = json.loads(error_records[0].split("ERROR:app.services.llm:")[-1])
        self.assertEqual(payload["event"], "llm_model_exhausted")
        self.assertIn("model", payload)


# ---------------------------------------------------------------------------
# Response field population
# ---------------------------------------------------------------------------

class TestResponseFields(unittest.IsolatedAsyncioTestCase):
    """LLMResponse returned by complete() has correct field types."""

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_DISPATCH_PATCH)
    @patch(_SETTINGS_PATCH)
    async def test_latency_ms_is_non_negative_int(self, mock_settings, mock_dispatch, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60
        mock_dispatch.return_value = _FAKE_RESPONSE

        result = await complete("s", [])
        self.assertIsInstance(result.latency_ms, int)
        self.assertGreaterEqual(result.latency_ms, 0)

    @patch(_SLEEP_PATCH, new_callable=AsyncMock)
    @patch(_DISPATCH_PATCH)
    @patch(_SETTINGS_PATCH)
    async def test_content_and_usage_forwarded(self, mock_settings, mock_dispatch, mock_sleep):
        mock_settings.LLM_MAX_RETRIES = 2
        mock_settings.LLM_BACKOFF_BASE = 1.0
        mock_settings.LLM_TIMEOUT_STANDARD = 30
        mock_settings.LLM_TIMEOUT_COMPLEX = 60
        mock_dispatch.return_value = LLMResponse(
            content="detailed feedback",
            usage=LLMUsage(input_tokens=200, output_tokens=100, cost_usd=0.01),
            latency_ms=0,
        )

        result = await complete("s", [])
        self.assertEqual(result.content, "detailed feedback")
        self.assertEqual(result.usage.input_tokens, 200)
        self.assertEqual(result.usage.output_tokens, 100)


# ---------------------------------------------------------------------------
# MODEL_CHAIN integrity
# ---------------------------------------------------------------------------

class TestModelChain(unittest.TestCase):
    def test_three_models_in_chain(self):
        self.assertEqual(len(MODEL_CHAIN), 3)

    def test_chain_order(self):
        names = [m.name for m in MODEL_CHAIN]
        self.assertEqual(names[0], "gemini-3.1-pro-preview")
        self.assertEqual(names[1], "gemini-3.1-flash-lite")
        self.assertEqual(names[2], "gpt-4o")

    def test_providers_correct(self):
        self.assertEqual(MODEL_CHAIN[0].provider, "gemini")
        self.assertEqual(MODEL_CHAIN[1].provider, "gemini")
        self.assertEqual(MODEL_CHAIN[2].provider, "openai")


if __name__ == "__main__":
    unittest.main()
