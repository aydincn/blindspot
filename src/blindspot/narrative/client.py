"""Minimal LLM provider clients over the standard library.

No provider SDKs — avoids dragging in `anthropic` or `litellm` just for one
JSON POST. The only third-party touch is `certifi` (a CA bundle, optional at
import time) so TLS verification works on macOS, where OpenSSL's default
trust store is empty. API keys are passed in explicitly (never read from
env); see `blindspot.narrative.config` for the source-of-truth precedence.
"""

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from functools import lru_cache

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

TIMEOUT_SECONDS = 30


@lru_cache(maxsize=1)
def _ssl_context() -> ssl.SSLContext:
    """TLS context for the API call.

    Python's default context verifies against the OpenSSL trust store,
    which on macOS (and some minimal Linux images) is often empty —
    producing `CERTIFICATE_VERIFY_FAILED` even with a valid API key. If
    `certifi` is installed we point at its CA bundle, which is the
    portable fix; otherwise we fall back to the system default.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class NarrativeError(RuntimeError):
    pass


class MissingAPIKey(NarrativeError):
    pass


@dataclass
class AnthropicClient:
    api_key: str
    model: str = DEFAULT_ANTHROPIC_MODEL
    max_tokens: int = 1500
    timeout: int = TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not self.api_key:
            raise MissingAPIKey("AnthropicClient requires a non-empty api_key.")
        if not self.model:
            self.model = DEFAULT_ANTHROPIC_MODEL

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        req = urllib.request.Request(
            ANTHROPIC_URL,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key or "",
                "anthropic-version": ANTHROPIC_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout, context=_ssl_context()
            ) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise NarrativeError(f"Anthropic API HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise NarrativeError(f"Anthropic API network error: {e.reason}") from e

        blocks = payload.get("content", [])
        text_parts = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        if not text_parts:
            raise NarrativeError(f"No text in Anthropic response: {payload}")
        return "".join(text_parts).strip()


@dataclass
class OpenAIClient:
    api_key: str
    model: str = DEFAULT_OPENAI_MODEL
    max_tokens: int = 1500
    timeout: int = TIMEOUT_SECONDS

    def __post_init__(self) -> None:
        if not self.api_key:
            raise MissingAPIKey("OpenAIClient requires a non-empty api_key.")
        if not self.model:
            self.model = DEFAULT_OPENAI_MODEL

    def complete(self, system: str, user: str) -> str:
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        req = urllib.request.Request(
            OPENAI_URL,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "authorization": f"Bearer {self.api_key}",
            },
        )
        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout, context=_ssl_context()
            ) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            raise NarrativeError(f"OpenAI API HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise NarrativeError(f"OpenAI API network error: {e.reason}") from e

        choices = payload.get("choices", [])
        if not choices:
            raise NarrativeError(f"No choices in OpenAI response: {payload}")
        content = (choices[0].get("message") or {}).get("content", "")
        if not content:
            raise NarrativeError(f"No content in OpenAI response: {payload}")
        return content.strip()


_Client = AnthropicClient | OpenAIClient


def build_client(provider: str, api_key: str, model: str = "") -> _Client | None:
    """Factory: pick a cloud provider client by name.

    Returns None when no api_key is provided — the caller falls back to
    the rule-based narrator. Anthropic and OpenAI are supported.
    """
    if not api_key:
        return None
    p = provider.lower().strip() or "anthropic"
    if p == "anthropic":
        return AnthropicClient(api_key=api_key, model=model or DEFAULT_ANTHROPIC_MODEL)
    if p == "openai":
        return OpenAIClient(api_key=api_key, model=model or DEFAULT_OPENAI_MODEL)
    raise NarrativeError(
        f"Unknown narrative provider '{provider}'. Supported: anthropic, openai."
    )


__all__ = [
    "AnthropicClient",
    "DEFAULT_ANTHROPIC_MODEL",
    "DEFAULT_OPENAI_MODEL",
    "MissingAPIKey",
    "NarrativeError",
    "OpenAIClient",
    "build_client",
]
