import subprocess
from unittest.mock import MagicMock, patch

import pytest

from blindspot.collector.github.client import RateLimitExhausted
from blindspot.collector.github.gh_client import (
    GhCliClient,
    is_gh_authenticated,
    is_gh_available,
    make_github_client,
)


def _gh_response(body: str, headers: dict[str, str] | None = None) -> str:
    headers = headers or {
        "X-RateLimit-Remaining": "4999",
        "X-RateLimit-Limit": "5000",
        "X-RateLimit-Reset": "1700000000",
    }
    header_lines = "HTTP/2.0 200 OK\n" + "\n".join(f"{k}: {v}" for k, v in headers.items())
    return f"{header_lines}\n\n{body}"


def test_is_gh_available_returns_true_when_command_succeeds():
    fake = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=fake):
        assert is_gh_available() is True


def test_is_gh_available_returns_false_when_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert is_gh_available() is False


def test_is_gh_authenticated_returns_false_when_not_logged_in():
    fake = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=fake):
        assert is_gh_authenticated() is False


def test_gh_client_get_parses_json_body_and_headers():
    fake = MagicMock(returncode=0, stdout=_gh_response('{"login": "tiangolo"}'), stderr="")
    with patch("subprocess.run", return_value=fake):
        data, rate = GhCliClient().get("/users/tiangolo")
    assert data["login"] == "tiangolo"
    assert rate.remaining == 4999
    assert rate.limit == 5000


def test_gh_client_raises_when_rate_limit_floor_breached():
    fake = MagicMock(
        returncode=0,
        stdout=_gh_response(
            "{}",
            headers={
                "X-RateLimit-Remaining": "10",
                "X-RateLimit-Limit": "5000",
                "X-RateLimit-Reset": "1700000000",
            },
        ),
        stderr="",
    )
    with patch("subprocess.run", return_value=fake):
        client = GhCliClient(min_remaining=50)
        with pytest.raises(RateLimitExhausted):
            client.get("/users/tiangolo")


def test_gh_client_raises_when_gh_returns_nonzero_with_rate_limit_message():
    fake = MagicMock(
        returncode=1,
        stdout="",
        stderr="HTTP 403: API rate limit exceeded for user ID",
    )
    with patch("subprocess.run", return_value=fake):
        with pytest.raises(RateLimitExhausted):
            GhCliClient().get("/users/tiangolo")


def test_gh_client_paginate_stops_on_partial_page():
    pages = [
        _gh_response('[' + ",".join(['{"id":' + str(i) + "}" for i in range(100)]) + "]"),
        _gh_response('[' + ",".join(['{"id":' + str(i) + "}" for i in range(100, 130)]) + "]"),
    ]
    responses = [MagicMock(returncode=0, stdout=p, stderr="") for p in pages]
    with patch("subprocess.run", side_effect=responses):
        items = list(GhCliClient().paginate("/repos/x/y/pulls", per_page=100))
    assert len(items) == 130


def test_make_github_client_falls_back_to_anonymous_when_gh_missing():
    with patch(
        "blindspot.collector.github.gh_client.is_gh_available", return_value=False
    ):
        client, backend = make_github_client(prefer_gh=True)
    assert backend == "anonymous"


def test_make_github_client_picks_gh_when_authenticated():
    with (
        patch(
            "blindspot.collector.github.gh_client.is_gh_available", return_value=True
        ),
        patch(
            "blindspot.collector.github.gh_client.is_gh_authenticated", return_value=True
        ),
    ):
        client, backend = make_github_client(prefer_gh=True)
    assert backend == "gh"
    assert isinstance(client, GhCliClient)


def test_make_github_client_uses_token_when_provided_and_gh_unavailable():
    with patch(
        "blindspot.collector.github.gh_client.is_gh_available", return_value=False
    ):
        client, backend = make_github_client(prefer_gh=True, token="ghp_fake")
    assert backend == "token"


_ = subprocess  # imported for clarity of what is being mocked
