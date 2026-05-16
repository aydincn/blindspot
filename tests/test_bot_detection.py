import pytest

from blindspot.collector.bots import is_bot_author


@pytest.mark.parametrize(
    "email,name",
    [
        ("dependabot[bot]@users.noreply.github.com", "dependabot[bot]"),
        ("49699333+dependabot[bot]@users.noreply.github.com", "dependabot[bot]"),
        ("github-actions[bot]@users.noreply.github.com", "github-actions[bot]"),
        ("renovate[bot]@users.noreply.github.com", "Renovate Bot"),
        ("mergify[bot]@users.noreply.github.com", ""),
        ("copilot@github", "copilot-swe-agent"),
        ("copilot-swe-agent@github", "Copilot Agent"),
        ("dependabot@github", "Dependabot"),
        ("pre-commit-ci[bot]@users.noreply.github.com", "pre-commit-ci[bot]"),
    ],
)
def test_detects_bot_identities(email, name):
    assert is_bot_author(email, name)


@pytest.mark.parametrize(
    "email,name",
    [
        ("alice@example.com", "Alice"),
        ("bob.smith@company.com", "Bob Smith"),
        ("123+willmcgugan@users.noreply.github.com", "Will McGugan"),
        ("willmcgugan@github", "Will McGugan"),
        ("tiangolo@gmail.com", "Sebastián Ramírez"),
    ],
)
def test_does_not_flag_humans_as_bots(email, name):
    assert not is_bot_author(email, name)


def test_handles_empty_inputs():
    assert not is_bot_author("", "")
    assert not is_bot_author("", "Some Name")


# ---------------------------------------------------------------------------
# Wider bot patterns (0.0.5d) — release robots, automation accounts, etc.

@pytest.mark.parametrize(
    "email,name",
    [
        # k8s release robot — caught Kubernetes head-line action regression
        ("k8s-release-robot@github", "Kubernetes Release Robot"),
        ("release-robot@github", "Release Robot"),
        ("automation@example.com", "Automation"),
        ("kubernetes-release-bot@github", "Kubernetes Release Bot"),
        ("ci-deploy@example.com", "CI Deploy"),
        # name-only path — email is generic
        ("noreply@github.com", "test-robot"),
        ("noreply@github.com", "bot-foo"),
    ],
)
def test_flags_broader_bot_patterns(email, name):
    assert is_bot_author(email, name)


@pytest.mark.parametrize(
    "email,name",
    [
        # "Roberto" should not be caught by *-robot* pattern
        ("roberto@example.com", "Roberto Garcia"),
        # "ci" word inside a normal name should not flag — boundary check
        ("lucia@example.com", "Lucia Smith"),
        # noreply.github.com with a real login is a human
        ("123+alice@users.noreply.github.com", "Alice"),
    ],
)
def test_does_not_overflag_humans(email, name):
    assert not is_bot_author(email, name)
