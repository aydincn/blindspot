"""
GitHub CLI (`gh`) client.

If the user has the `gh` CLI installed and authenticated (`gh auth login`),
this client routes API calls through `gh api`. Benefits:

* No token management — uses the gh CLI's own credentials.
* 5000/hr rate limit instead of 60/hr anonymous.
* Works with GitHub Enterprise out of the box if gh is configured for it.
"""

import json
import re
import subprocess
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from blindspot.collector.github.client import (
    GitHubError,
    RateLimitExhausted,
    RateLimitStatus,
)


def is_gh_available() -> bool:
    try:
        result = subprocess.run(
            ["gh", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def is_gh_authenticated() -> bool:
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


@dataclass
class GhCliClient:
    min_remaining: int = 50

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> tuple[Any, RateLimitStatus]:
        full_path = self._build_path(path, params)
        cmd = ["gh", "api", "-i", "-X", "GET", full_path]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False, timeout=60
            )
        except subprocess.TimeoutExpired as e:
            raise GitHubError(f"gh api timed out for {full_path}") from e
        except FileNotFoundError as e:
            raise GitHubError("gh CLI is not installed.") from e

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if "rate limit" in stderr.lower() or "rate_limit" in stderr.lower():
                raise RateLimitExhausted(stderr)
            raise GitHubError(f"gh api failed: {stderr or 'unknown error'}")

        headers, body = _split_response(result.stdout)
        rate = _parse_rate_limit(headers)
        if rate.remaining < self.min_remaining:
            raise RateLimitExhausted(
                f"gh API rate limit nearly exhausted ({rate.remaining}/{rate.limit}).",
                reset_at=rate.reset_at,
            )

        try:
            data = json.loads(body) if body.strip() else None
        except json.JSONDecodeError as e:
            raise GitHubError(f"gh api returned non-JSON: {body[:200]}") from e
        return data, rate

    def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int = 100,
    ) -> Iterator[Any]:
        merged = dict(params or {})
        merged["per_page"] = per_page
        page = 1
        while page <= max_pages:
            merged["page"] = page
            data, _ = self.get(path, merged)
            if not isinstance(data, list):
                yield data
                return
            if not data:
                return
            yield from data
            if len(data) < per_page:
                return
            page += 1

    def _build_path(self, path: str, params: dict[str, Any] | None) -> str:
        if not params:
            return path
        encoded = urlencode(
            {k: v for k, v in params.items() if v is not None}, doseq=True
        )
        sep = "&" if "?" in path else "?"
        return f"{path}{sep}{encoded}"


def _split_response(text: str) -> tuple[str, str]:
    for sep in ("\r\n\r\n", "\n\n"):
        idx = text.find(sep)
        if idx != -1:
            return text[:idx], text[idx + len(sep):]
    return "", text


def _parse_rate_limit(headers: str) -> RateLimitStatus:
    remaining = _header(headers, "x-ratelimit-remaining", "0")
    limit = _header(headers, "x-ratelimit-limit", "0")
    reset = _header(headers, "x-ratelimit-reset", "0")
    return RateLimitStatus(
        remaining=int(remaining) if remaining.isdigit() else 0,
        limit=int(limit) if limit.isdigit() else 0,
        reset_at=int(reset) if reset.isdigit() else 0,
    )


def _header(blob: str, name: str, default: str) -> str:
    pattern = re.compile(rf"^{re.escape(name)}:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
    m = pattern.search(blob)
    return m.group(1).strip() if m else default


def make_github_client(
    prefer_gh: bool = True,
    token: str | None = None,
) -> tuple[Any, str]:
    """Return (client, backend_label).

    backend_label is one of: 'gh', 'token', 'anonymous'.
    """
    from blindspot.collector.github.client import GitHubClient

    if prefer_gh and is_gh_available() and is_gh_authenticated():
        return GhCliClient(), "gh"
    if token:
        return GitHubClient(token=token), "token"
    return GitHubClient(), "anonymous"


__all__ = [
    "GhCliClient",
    "is_gh_authenticated",
    "is_gh_available",
    "make_github_client",
]
