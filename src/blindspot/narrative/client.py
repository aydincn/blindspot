"""Minimal LLM provider clients using only the standard library.

No third-party deps — avoids dragging in `anthropic` or `litellm` just for one
JSON POST. API keys are passed in explicitly (never read from env); see
`blindspot.narrative.config` for the source-of-truth precedence.
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
TIMEOUT_SECONDS = 30


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
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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


def build_client(provider: str, api_key: str, model: str = "") -> AnthropicClient:
    """Factory: pick a provider client by name.

    Currently supports `anthropic`. Add new providers here.
    """
    p = provider.lower().strip()
    if p == "anthropic":
        return AnthropicClient(api_key=api_key, model=model or DEFAULT_ANTHROPIC_MODEL)
    raise NarrativeError(
        f"Unknown narrative provider '{provider}'. Supported: anthropic."
    )


__all__ = [
    "AnthropicClient",
    "DEFAULT_ANTHROPIC_MODEL",
    "MissingAPIKey",
    "NarrativeError",
    "build_client",
]
