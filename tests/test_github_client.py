import io
import json
from unittest.mock import patch

import pytest

from blindspot.collector.github.client import GitHubClient, RateLimitExhausted


def _fake_response(body, headers=None):
    headers = headers or {
        "X-RateLimit-Remaining": "50",
        "X-RateLimit-Limit": "60",
        "X-RateLimit-Reset": "1700000000",
    }
    resp = io.BytesIO(json.dumps(body).encode("utf-8"))
    resp.__enter__ = lambda self: self  # type: ignore[method-assign]
    resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
    resp.headers = headers
    return resp


def test_get_returns_payload_and_rate_status():
    fake = _fake_response({"login": "tiangolo"})
    with patch("urllib.request.urlopen", return_value=fake):
        client = GitHubClient()
        data, status = client.get("/users/tiangolo")
    assert data["login"] == "tiangolo"
    assert status.remaining == 50
    assert status.limit == 60


def test_get_raises_when_remaining_below_floor():
    fake = _fake_response(
        {"ok": True},
        headers={
            "X-RateLimit-Remaining": "1",
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Reset": "1700000000",
        },
    )
    with patch("urllib.request.urlopen", return_value=fake):
        client = GitHubClient(min_remaining=2)
        with pytest.raises(RateLimitExhausted):
            client.get("/users/tiangolo")


def test_paginate_stops_when_page_partial():
    page1 = _fake_response([{"id": i} for i in range(100)])
    page2 = _fake_response([{"id": i} for i in range(100, 150)])

    responses = [page1, page2]
    with patch("urllib.request.urlopen", side_effect=responses):
        client = GitHubClient()
        items = list(client.paginate("/repos/x/y/pulls", per_page=100))
    assert len(items) == 150


def test_paginate_stops_when_empty():
    page1 = _fake_response([{"id": 1}, {"id": 2}])
    page2 = _fake_response([])

    responses = [page1, page2]
    with patch("urllib.request.urlopen", side_effect=responses):
        client = GitHubClient()
        items = list(client.paginate("/repos/x/y/pulls", per_page=100))
    assert len(items) == 2
