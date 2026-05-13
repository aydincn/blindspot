"""Detect automated authors (bots, CI agents, AI coding agents) by their identity."""

import re

# GitHub's own bot-naming convention: <name>[bot]
_BOT_SUFFIX = re.compile(r"\[bot\]", re.IGNORECASE)

# Well-known bot login/email fragments (case-insensitive). Conservative list —
# false positives push real humans into a wrong bucket, so we err on the side
# of clearly automated identities.
_KNOWN_BOT_FRAGMENTS = frozenset(
    {
        "dependabot",
        "renovate-bot",
        "renovatebot",
        "renovate[bot]",
        "github-actions",
        "github-actions[bot]",
        "mergify",
        "mergify[bot]",
        "pre-commit-ci",
        "imgbot",
        "allcontributors",
        "snyk-bot",
        "greenkeeper",
        "stale[bot]",
        # GitHub AI coding agents
        "copilot",
        "copilot-swe-agent",
        "copilot[bot]",
    }
)

# Canonical domains that always indicate automation.
_BOT_DOMAINS = frozenset(
    {
        "bots.noreply.github.com",
        "bots.github.com",
    }
)


def is_bot_author(email: str, name: str = "") -> bool:
    """Return True when the author appears to be automated, not a person."""
    email = (email or "").lower()
    name = (name or "").lower()

    if _BOT_SUFFIX.search(name) or _BOT_SUFFIX.search(email):
        return True

    if name and name in _KNOWN_BOT_FRAGMENTS:
        return True

    if "@" in email:
        local, domain = email.split("@", 1)
        if domain in _BOT_DOMAINS:
            return True
        # canonical_email rewrites `123+login@users.noreply.github.com` to `login@github`
        # so we check the local part against known bot fragments.
        if local in _KNOWN_BOT_FRAGMENTS:
            return True

    return False


__all__ = ["is_bot_author"]
