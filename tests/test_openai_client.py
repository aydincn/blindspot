"""OpenAI client tests — mocks urllib at the urlopen boundary."""

import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from blindspot.narrative.client import (
    DEFAULT_OPENAI_MODEL,
    MissingAPIKey,
    NarrativeError,
    OpenAIClient,
    build_client,
)


def _resp(body: dict) -> io.BytesIO:
    resp = io.BytesIO(json.dumps(body).encode("utf-8"))
    resp.__enter__ = lambda self: self  # type: ignore[method-assign]
    resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
    return resp


def test_openai_client_missing_key_raises():
    with pytest.raises(MissingAPIKey):
        OpenAIClient(api_key="")


def test_openai_client_complete_happy_path():
    body = {
        "choices": [
            {"message": {"content": "{\"executive_summary\": \"…\"}"}, "index": 0}
        ]
    }
    with patch("urllib.request.urlopen", return_value=_resp(body)):
        client = OpenAIClient(api_key="sk-test", model="gpt-4o-mini")
        out = client.complete("system msg", "user msg")
    assert "executive_summary" in out


def test_openai_client_uses_default_model_when_blank():
    client = OpenAIClient(api_key="sk-test", model="")
    assert client.model == DEFAULT_OPENAI_MODEL


def test_openai_client_http_error_raises_narrative_error():
    err = urllib.error.HTTPError(
        url="https://api.openai.com/v1/chat/completions",
        code=401,
        msg="Unauthorized",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b'{"error":"bad key"}'),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        client = OpenAIClient(api_key="sk-bad", model="gpt-4o-mini")
        with pytest.raises(NarrativeError):
            client.complete("s", "u")


def test_build_client_returns_none_when_no_key():
    assert build_client("anthropic", "") is None
    assert build_client("openai", "") is None


def test_build_client_picks_openai():
    c = build_client("openai", "sk-test", "gpt-4o-mini")
    assert isinstance(c, OpenAIClient)
    assert c.model == "gpt-4o-mini"


def test_build_client_picks_anthropic_by_default():
    from blindspot.narrative.client import AnthropicClient
    c = build_client("", "sk-ant-test", "")
    assert isinstance(c, AnthropicClient)


def test_build_client_rejects_unknown_provider():
    with pytest.raises(NarrativeError):
        build_client("gemini", "key", "")
