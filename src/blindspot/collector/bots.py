"""Detect automated authors (bots, CI agents, AI coding agents) by their identity."""

import re

# GitHub's own bot-naming convention: <name>[bot]
_BOT_SUFFIX = re.compile(r"\[bot\]", re.IGNORECASE)

# Generic identity patterns. Matched against the author's name *and* the
# email local-part (the bit before the @). We keep this conservative — a
# false positive moves a real human into "bot" and silently erases their
# contributions from every metric — but the patterns below all describe
# automation identities that humans almost never claim.
_BOT_IDENTITY_RE = re.compile(
    r"(?:"
    r"\[bot\]"                  # foo[bot]
    r"|(?:^|[-_./])bot(?:[-_./]|$)"   # bot-foo, foo-bot, foo_bot, bot.foo
    r"|(?:^|[-_./])robot(?:[-_./]|$)"  # *-robot, robot-*, release-robot
    r"|^automation(?:[-_./]|$)"  # automation@..., automation-foo
    r"|^ci(?:[-_./])"            # ci-deploy, ci.runner — keep loose
    r")",
    re.IGNORECASE,
)

# Well-known bot login/email fragments (case-insensitive). Kept for
# pin-point identification of well-known services whose names don't fit
# the generic pattern above.
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

    # Generic pattern check on the name and email local-part.
    if name and _BOT_IDENTITY_RE.search(name):
        return True

    if name and name in _KNOWN_BOT_FRAGMENTS:
        return True

    if "@" in email:
        local, domain = email.split("@", 1)
        if domain in _BOT_DOMAINS:
            return True
        # canonical_email rewrites `123+login@users.noreply.github.com` to
        # `login@github` so we check the local part against both known
        # fragments and the generic pattern.
        if local in _KNOWN_BOT_FRAGMENTS:
            return True
        if _BOT_IDENTITY_RE.search(local):
            return True

    return False


__all__ = ["is_bot_author"]
