"""
Minimal GitHub REST client.

Designed for anonymous, public-repo use. Anonymous requests are rate-limited
to 60/hour by GitHub; the client surfaces remaining quota and raises
``RateLimitExhausted`` rather than silently failing.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

API_ROOT = "https://api.github.com"
DEFAULT_USER_AGENT = "blindspot/0.0.2"


class GitHubError(RuntimeError):
    pass


class RateLimitExhausted(GitHubError):
    def __init__(self, message: str, reset_at: int | None = None) -> None:
        super().__init__(message)
        self.reset_at = reset_at


@dataclass
class RateLimitStatus:
    remaining: int
    limit: int
    reset_at: int


@dataclass
class GitHubClient:
    token: str | None = None
    user_agent: str = DEFAULT_USER_AGENT
    min_remaining: int = 2

    def get(self, path: str, params: dict[str, Any] | None = None) -> tuple[Any, RateLimitStatus]:
        url = self._build_url(path, params)
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        req.add_header("User-Agent", self.user_agent)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
                status = _rate_limit_from_headers(resp.headers)
        except urllib.error.HTTPError as e:
            if e.code == 403 and "rate limit" in (e.read().decode("utf-8", "replace")).lower():
                raise RateLimitExhausted("GitHub rate limit exhausted.") from e
            raise GitHubError(f"GitHub API error {e.code} for {url}") from e
        except urllib.error.URLError as e:
            raise GitHubError(f"Network error talking to {url}: {e.reason}") from e

        if status.remaining < self.min_remaining:
            raise RateLimitExhausted(
                f"GitHub rate limit nearly exhausted ({status.remaining}/{status.limit}).",
                reset_at=status.reset_at,
            )
        return payload, status

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

    def _build_url(self, path: str, params: dict[str, Any] | None) -> str:
        if path.startswith("http"):
            base = path
        else:
            base = f"{API_ROOT}{path if path.startswith('/') else '/' + path}"
        if not params:
            return base
        encoded = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}, doseq=True
        )
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{encoded}"


def _rate_limit_from_headers(headers: Any) -> RateLimitStatus:
    remaining = int(headers.get("X-RateLimit-Remaining", "0") or 0)
    limit = int(headers.get("X-RateLimit-Limit", "0") or 0)
    reset = int(headers.get("X-RateLimit-Reset", "0") or 0)
    return RateLimitStatus(remaining=remaining, limit=limit, reset_at=reset)


_ = time  # reserved for future backoff support
