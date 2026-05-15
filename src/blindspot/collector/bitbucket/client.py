"""Minimal Bitbucket Cloud REST API v2.0 client.

Basic-auth with a username + app password. Bitbucket's pagination is
cursor-style: each response carries a full `next` URL, so `paginate`
follows that rather than incrementing a page number.

Bitbucket Cloud rate limits are generous (~1000 req/hr for authed
requests) and not surfaced in headers as cleanly as GitHub's, so this
client raises `BitbucketError` on HTTP failures but doesn't model a
quota the way the GitHub client does.
"""

import base64
import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

API_ROOT = "https://api.bitbucket.org/2.0"
DEFAULT_USER_AGENT = "blindspot/0.0.3"


class BitbucketError(RuntimeError):
    pass


class BitbucketAuthError(BitbucketError):
    pass


@dataclass
class BitbucketClient:
    username: str
    app_password: str
    user_agent: str = DEFAULT_USER_AGENT

    def _auth_header(self) -> str:
        raw = f"{self.username}:{self.app_password}".encode()
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def get(self, path_or_url: str, params: dict[str, Any] | None = None) -> Any:
        url = self._build_url(path_or_url, params)
        req = urllib.request.Request(url, method="GET")
        req.add_header("Accept", "application/json")
        req.add_header("User-Agent", self.user_agent)
        req.add_header("Authorization", self._auth_header())

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise BitbucketAuthError(
                    f"Bitbucket auth failed ({e.code}) — check the username "
                    f"and app password (needs pullrequest:read + repository:read)."
                ) from e
            if e.code == 404:
                raise BitbucketError(
                    f"Bitbucket resource not found (404): {url}"
                ) from e
            raise BitbucketError(
                f"Bitbucket API error {e.code} for {url}"
            ) from e
        except urllib.error.URLError as e:
            raise BitbucketError(
                f"Network error talking to {url}: {e.reason}"
            ) from e

    def paginate(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        pagelen: int = 50,
        max_pages: int = 100,
    ) -> Iterator[Any]:
        """Yield items across Bitbucket's cursor-paginated responses.

        Bitbucket wraps list responses as `{values: [...], next: "<url>"}`.
        We follow `next` until it's absent or `max_pages` is hit.
        """
        merged = dict(params or {})
        merged["pagelen"] = pagelen
        url: str | None = self._build_url(path, merged)
        pages = 0
        while url and pages < max_pages:
            data = self.get(url)
            if not isinstance(data, dict):
                # Non-list endpoint returned a bare object.
                yield data
                return
            values = data.get("values")
            if isinstance(values, list):
                yield from values
            else:
                yield data
                return
            url = data.get("next")
            pages += 1

    def _build_url(self, path_or_url: str, params: dict[str, Any] | None) -> str:
        if path_or_url.startswith("http"):
            base = path_or_url
        else:
            base = f"{API_ROOT}{path_or_url if path_or_url.startswith('/') else '/' + path_or_url}"
        if not params:
            return base
        encoded = urllib.parse.urlencode(
            {k: v for k, v in params.items() if v is not None}, doseq=True
        )
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{encoded}"


__all__ = ["API_ROOT", "BitbucketAuthError", "BitbucketClient", "BitbucketError"]
