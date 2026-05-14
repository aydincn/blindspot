"""BitbucketClient tests — mocks urllib at the urlopen boundary."""

import base64
import io
import json
import urllib.error
from unittest.mock import patch

import pytest

from blindspot.collector.bitbucket.client import (
    BitbucketAuthError,
    BitbucketClient,
    BitbucketError,
)


def _resp(body: object) -> io.BytesIO:
    resp = io.BytesIO(json.dumps(body).encode("utf-8"))
    resp.__enter__ = lambda self: self  # type: ignore[method-assign]
    resp.__exit__ = lambda *a: False  # type: ignore[method-assign]
    return resp


def test_auth_header_is_basic_base64():
    client = BitbucketClient(username="alice", app_password="secret")
    header = client._auth_header()
    assert header.startswith("Basic ")
    decoded = base64.b64decode(header.removeprefix("Basic ")).decode()
    assert decoded == "alice:secret"


def test_paginate_follows_next_url():
    page1 = {"values": [{"id": 1}, {"id": 2}], "next": "https://api.bitbucket.org/2.0/x?page=2"}
    page2 = {"values": [{"id": 3}], "next": None}
    responses = [_resp(page1), _resp(page2)]

    with patch("urllib.request.urlopen", side_effect=responses):
        client = BitbucketClient(username="u", app_password="p")
        items = list(client.paginate("/repositories/ws/repo/pullrequests"))

    assert [i["id"] for i in items] == [1, 2, 3]


def test_paginate_stops_without_next():
    page = {"values": [{"id": 1}]}  # no "next" key
    with patch("urllib.request.urlopen", side_effect=[_resp(page)]):
        client = BitbucketClient(username="u", app_password="p")
        items = list(client.paginate("/x"))
    assert [i["id"] for i in items] == [1]


def test_401_raises_auth_error():
    err = urllib.error.HTTPError(
        url="https://api.bitbucket.org/2.0/x",
        code=401,
        msg="Unauthorized",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b""),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        client = BitbucketClient(username="u", app_password="bad")
        with pytest.raises(BitbucketAuthError):
            client.get("/x")


def test_404_raises_bitbucket_error():
    err = urllib.error.HTTPError(
        url="https://api.bitbucket.org/2.0/x",
        code=404,
        msg="Not Found",
        hdrs=None,  # type: ignore[arg-type]
        fp=io.BytesIO(b""),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        client = BitbucketClient(username="u", app_password="p")
        with pytest.raises(BitbucketError):
            client.get("/x")
