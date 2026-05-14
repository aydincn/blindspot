import pytest

from blindspot.collector.bitbucket.remote import parse_remote_url


@pytest.mark.parametrize(
    "url,workspace,repo",
    [
        ("https://bitbucket.org/myteam/myrepo", "myteam", "myrepo"),
        ("https://bitbucket.org/myteam/myrepo.git", "myteam", "myrepo"),
        ("https://bitbucket.org/myteam/myrepo/", "myteam", "myrepo"),
        ("http://bitbucket.org/myteam/myrepo", "myteam", "myrepo"),
        # HTTPS with embedded username (Bitbucket app-password clone URLs).
        ("https://alice@bitbucket.org/myteam/myrepo.git", "myteam", "myrepo"),
        ("git@bitbucket.org:myteam/myrepo.git", "myteam", "myrepo"),
        ("git@bitbucket.org:myteam/myrepo", "myteam", "myrepo"),
        ("ssh://git@bitbucket.org/myteam/myrepo.git", "myteam", "myrepo"),
    ],
)
def test_parses_various_bitbucket_url_forms(url, workspace, repo):
    parsed = parse_remote_url(url)
    assert parsed is not None
    assert parsed.workspace == workspace
    assert parsed.repo == repo
    assert parsed.slug == f"{workspace}/{repo}"


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/foo/bar",
        "git@github.com:foo/bar.git",
        "https://gitlab.com/foo/bar",
        # Self-hosted Bitbucket Server — different API, intentionally not matched.
        "https://bitbucket.mycompany.com/scm/proj/repo.git",
        "not-a-url",
        "",
    ],
)
def test_returns_none_for_non_bitbucket_cloud_urls(url):
    assert parse_remote_url(url) is None
