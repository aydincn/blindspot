import pytest

from blindspot.collector.github.remote import parse_remote_url


@pytest.mark.parametrize(
    "url,owner,repo",
    [
        ("https://github.com/tiangolo/fastapi", "tiangolo", "fastapi"),
        ("https://github.com/tiangolo/fastapi.git", "tiangolo", "fastapi"),
        ("https://github.com/tiangolo/fastapi/", "tiangolo", "fastapi"),
        ("http://github.com/tiangolo/fastapi", "tiangolo", "fastapi"),
        ("git@github.com:tiangolo/fastapi.git", "tiangolo", "fastapi"),
        ("git@github.com:tiangolo/fastapi", "tiangolo", "fastapi"),
        ("ssh://git@github.com/tiangolo/fastapi.git", "tiangolo", "fastapi"),
        ("https://github.com/Textualize/rich.git", "Textualize", "rich"),
    ],
)
def test_parses_various_github_url_forms(url, owner, repo):
    parsed = parse_remote_url(url)
    assert parsed is not None
    assert parsed.owner == owner
    assert parsed.repo == repo
    assert parsed.slug == f"{owner}/{repo}"


@pytest.mark.parametrize(
    "url",
    [
        "https://gitlab.com/foo/bar",
        "https://bitbucket.org/foo/bar",
        "not-a-url",
        "",
    ],
)
def test_returns_none_for_non_github_urls(url):
    assert parse_remote_url(url) is None
