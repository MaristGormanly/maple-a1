"""Unit tests for the real LLM provider dispatch functions (_call_gemini, _call_openai).

Mocks the openai.OpenAI client so no real API calls are made.
"""

import unittest
from unittest.mock import MagicMock, patch

from app.services.llm import (
    EvaluationFailedError,
    LLMResponse,
    LLMUsage,
    ModelSpec,
    ProviderError,
    _call_gemini,
    _call_openai,
    _dispatch,
)

_SETTINGS_PATCH = "app.services.llm.settings"
_OPENAI_PATCH = "openai.OpenAI"


def _make_openai_response(content="ok", prompt_tokens=10, completion_tokens=5):
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    choice = MagicMock()
    choice.message.content = content
    resp = MagicMock()
    resp.choices = [choice]
    resp.usage = usage
    return resp


_SPEC_GEMINI = ModelSpec(name="gemini-3.1-pro-preview", provider="gemini")
_SPEC_OPENAI = ModelSpec(name="gpt-4o", provider="openai")


class TestCallOpenAINoKey(unittest.TestCase):
    """_call_openai raises ProviderError when OPENAI_API_KEY is absent."""

    @patch(_SETTINGS_PATCH)
    def test_raises_when_key_is_none(self, mock_settings):
        mock_settings.OPENAI_API_KEY = None
        with self.assertRaises(ProviderError) as ctx:
            _call_openai(_SPEC_OPENAI, "sys", [], 512, 0.7)
        self.assertIn("OPENAI_API_KEY", str(ctx.exception))

    @patch(_SETTINGS_PATCH)
    def test_raises_when_key_is_empty(self, mock_settings):
        mock_settings.OPENAI_API_KEY = ""
        with self.assertRaises(ProviderError):
            _call_openai(_SPEC_OPENAI, "sys", [], 512, 0.7)


class TestCallOpenAISuccess(unittest.TestCase):
    """_call_openai returns a populated LLMResponse on success."""

    @patch(_OPENAI_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_returns_llm_response(self, mock_settings, MockOpenAI):
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_openai_response(
            content="great code", prompt_tokens=20, completion_tokens=8
        )

        result = _call_openai(_SPEC_OPENAI, "system", [{"role": "user", "content": "hi"}], 512, 0.7)

        self.assertIsInstance(result, LLMResponse)
        self.assertEqual(result.content, "great code")
        self.assertEqual(result.usage.input_tokens, 20)
        self.assertEqual(result.usage.output_tokens, 8)

    @patch(_OPENAI_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_passes_model_name_and_params(self, mock_settings, MockOpenAI):
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_openai_response()

        _call_openai(_SPEC_OPENAI, "sys", [{"role": "user", "content": "q"}], 256, 0.5)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs["model"], "gpt-4o")
        self.assertEqual(call_kwargs["max_tokens"], 256)
        self.assertEqual(call_kwargs["temperature"], 0.5)

    @patch(_OPENAI_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_system_prompt_prepended_to_messages(self, mock_settings, MockOpenAI):
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_openai_response()

        _call_openai(_SPEC_OPENAI, "be helpful", [{"role": "user", "content": "q"}], 128, 0.7)

        msgs = mock_client.chat.completions.create.call_args.kwargs["messages"]
        self.assertEqual(msgs[0], {"role": "system", "content": "be helpful"})
        self.assertEqual(msgs[1], {"role": "user", "content": "q"})

    @patch(_OPENAI_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_none_content_coerced_to_empty_string(self, mock_settings, MockOpenAI):
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        resp = _make_openai_response()
        resp.choices[0].message.content = None
        mock_client.chat.completions.create.return_value = resp

        result = _call_openai(_SPEC_OPENAI, "sys", [], 128, 0.7)

        self.assertEqual(result.content, "")

    @patch(_OPENAI_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_none_usage_yields_zero_tokens(self, mock_settings, MockOpenAI):
        mock_settings.OPENAI_API_KEY = "sk-test"
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        resp = _make_openai_response()
        resp.usage = None
        mock_client.chat.completions.create.return_value = resp

        result = _call_openai(_SPEC_OPENAI, "sys", [], 128, 0.7)

        self.assertEqual(result.usage.input_tokens, 0)
        self.assertEqual(result.usage.output_tokens, 0)


class TestCallGeminiNoKey(unittest.TestCase):
    """_call_gemini raises ProviderError when GEMINI_API_KEY is absent."""

    @patch(_SETTINGS_PATCH)
    def test_raises_when_key_is_none(self, mock_settings):
        mock_settings.GEMINI_API_KEY = None
        with self.assertRaises(ProviderError) as ctx:
            _call_gemini(_SPEC_GEMINI, "sys", [], 512, 0.7)
        self.assertIn("GEMINI_API_KEY", str(ctx.exception))

    @patch(_SETTINGS_PATCH)
    def test_raises_when_key_is_empty(self, mock_settings):
        mock_settings.GEMINI_API_KEY = ""
        with self.assertRaises(ProviderError):
            _call_gemini(_SPEC_GEMINI, "sys", [], 512, 0.7)


class TestCallGeminiSuccess(unittest.TestCase):
    """_call_gemini uses OpenAI-compatible Gemini endpoint and returns LLMResponse."""

    @patch(_OPENAI_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_uses_gemini_base_url(self, mock_settings, MockOpenAI):
        mock_settings.GEMINI_API_KEY = "gemini-key"
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_openai_response()

        _call_gemini(_SPEC_GEMINI, "sys", [], 512, 0.7)

        init_kwargs = MockOpenAI.call_args.kwargs
        self.assertIn("generativelanguage.googleapis.com", init_kwargs.get("base_url", ""))

    @patch(_OPENAI_PATCH)
    @patch(_SETTINGS_PATCH)
    def test_returns_llm_response(self, mock_settings, MockOpenAI):
        mock_settings.GEMINI_API_KEY = "gemini-key"
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = _make_openai_response(
            content="gemini says hi", prompt_tokens=15, completion_tokens=3
        )

        result = _call_gemini(_SPEC_GEMINI, "sys", [], 512, 0.7)

        self.assertEqual(result.content, "gemini says hi")
        self.assertEqual(result.usage.input_tokens, 15)
        self.assertEqual(result.usage.output_tokens, 3)


class TestDispatchRouting(unittest.TestCase):
    """_dispatch routes to the correct provider based on spec.provider."""

    @patch(_SETTINGS_PATCH)
    def test_unknown_provider_raises(self, mock_settings):
        spec = ModelSpec(name="mystery-model", provider="unknown")
        with self.assertRaises(ProviderError) as ctx:
            _dispatch(spec, "sys", [], 512, 0.7)
        self.assertIn("Unknown provider", str(ctx.exception))

    @patch("app.services.llm._call_openai")
    def test_openai_provider_routes_to_call_openai(self, mock_call):
        mock_call.return_value = MagicMock()
        _dispatch(_SPEC_OPENAI, "s", [], 128, 0.5)
        mock_call.assert_called_once()

    @patch("app.services.llm._call_gemini")
    def test_gemini_provider_routes_to_call_gemini(self, mock_call):
        mock_call.return_value = MagicMock()
        _dispatch(_SPEC_GEMINI, "s", [], 128, 0.5)
        mock_call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
