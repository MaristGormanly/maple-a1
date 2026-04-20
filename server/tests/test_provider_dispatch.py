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


def _make_gemini_response(text="ok", prompt_tokens=10, candidates_tokens=5, status_code=200):
    """Build a fake httpx.Response for the native Gemini generateContent endpoint."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": text}], "role": "model"}}],
        "usageMetadata": {
            "promptTokenCount": prompt_tokens,
            "candidatesTokenCount": candidates_tokens,
            "totalTokenCount": prompt_tokens + candidates_tokens,
        },
    }
    return resp


_HTTPX_POST = "httpx.post"


class TestCallGeminiSuccess(unittest.TestCase):
    """_call_gemini hits the native Gemini generateContent endpoint."""

    @patch(_HTTPX_POST)
    @patch(_SETTINGS_PATCH)
    def test_uses_native_endpoint_url(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = "gemini-key"
        mock_post.return_value = _make_gemini_response()

        _call_gemini(_SPEC_GEMINI, "sys", [], 512, 0.7)

        url = mock_post.call_args.args[0]
        self.assertIn("generativelanguage.googleapis.com", url)
        self.assertIn(":generateContent", url)
        self.assertIn(_SPEC_GEMINI.name, url)

    @patch(_HTTPX_POST)
    @patch(_SETTINGS_PATCH)
    def test_uses_x_goog_api_key_header(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = "gemini-key-xyz"
        mock_post.return_value = _make_gemini_response()

        _call_gemini(_SPEC_GEMINI, "sys", [], 512, 0.7)

        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(headers.get("x-goog-api-key"), "gemini-key-xyz")
        self.assertNotIn("Authorization", headers)

    @patch(_HTTPX_POST)
    @patch(_SETTINGS_PATCH)
    def test_system_prompt_in_systemInstruction(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = "k"
        mock_post.return_value = _make_gemini_response()

        _call_gemini(_SPEC_GEMINI, "be helpful", [{"role": "user", "content": "hi"}], 32, 0.5)

        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["systemInstruction"]["parts"][0]["text"], "be helpful")
        self.assertEqual(body["contents"][0]["role"], "user")
        self.assertEqual(body["contents"][0]["parts"][0]["text"], "hi")

    @patch(_HTTPX_POST)
    @patch(_SETTINGS_PATCH)
    def test_assistant_role_mapped_to_model(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = "k"
        mock_post.return_value = _make_gemini_response()

        _call_gemini(
            _SPEC_GEMINI, "",
            [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
            32, 0.5,
        )

        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["contents"][0]["role"], "user")
        self.assertEqual(body["contents"][1]["role"], "model")

    @patch(_HTTPX_POST)
    @patch(_SETTINGS_PATCH)
    def test_generation_config_passed(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = "k"
        mock_post.return_value = _make_gemini_response()

        _call_gemini(_SPEC_GEMINI, "", [], 256, 0.3)

        cfg = mock_post.call_args.kwargs["json"]["generationConfig"]
        self.assertEqual(cfg["maxOutputTokens"], 256)
        self.assertEqual(cfg["temperature"], 0.3)

    @patch(_HTTPX_POST)
    @patch(_SETTINGS_PATCH)
    def test_returns_llm_response(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = "k"
        mock_post.return_value = _make_gemini_response(
            text="gemini says hi", prompt_tokens=15, candidates_tokens=3
        )

        result = _call_gemini(_SPEC_GEMINI, "sys", [], 512, 0.7)

        self.assertEqual(result.content, "gemini says hi")
        self.assertEqual(result.usage.input_tokens, 15)
        self.assertEqual(result.usage.output_tokens, 3)

    @patch(_HTTPX_POST)
    @patch(_SETTINGS_PATCH)
    def test_non_200_raises_provider_error(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = "k"
        mock_post.return_value = _make_gemini_response(status_code=429, text="quota exceeded")

        with self.assertRaises(ProviderError) as ctx:
            _call_gemini(_SPEC_GEMINI, "sys", [], 32, 0.5)
        self.assertIn("429", str(ctx.exception))

    @patch(_HTTPX_POST)
    @patch(_SETTINGS_PATCH)
    def test_empty_candidates_raises_provider_error(self, mock_settings, mock_post):
        mock_settings.GEMINI_API_KEY = "k"
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"candidates": []}
        mock_post.return_value = resp

        with self.assertRaises(ProviderError):
            _call_gemini(_SPEC_GEMINI, "sys", [], 32, 0.5)


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
