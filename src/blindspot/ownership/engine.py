import math
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

from blindspot.collector.models import Commit
from blindspot.config import OwnershipWeights
from blindspot.ownership.models import FileOwnership, OwnershipMap
from blindspot.review_graph.engine import ReviewGraph


@dataclass
class _Agg:
    file: str
    email: str
    commit_count: int = 0
    additions: int = 0
    deletions: int = 0
    weighted_count: float = 0.0
    weighted_volume: float = 0.0
    last_authored_at: datetime | None = None
    review_score: float = 0.0
    last_name: str = ""


@dataclass
class OwnershipEngine:
    weights: OwnershipWeights = field(default_factory=OwnershipWeights)
    as_of: datetime | None = None

    def __post_init__(self) -> None:
        self.as_of = (self.as_of or datetime.now(UTC)).astimezone(UTC)

    def compute(
        self,
        commits: Iterable[Commit],
        review_graph: ReviewGraph | None = None,
    ) -> OwnershipMap:
        aggs: dict[tuple[str, str], _Agg] = {}
        names_by_email: dict[str, tuple[str, datetime]] = {}
        assert self.as_of is not None
        for c in commits:
            if c.author_name:
                prev = names_by_email.get(c.author_email)
                if prev is None or c.authored_at > prev[1]:
                    names_by_email[c.author_email] = (c.author_name, c.authored_at)

            days_since_commit = max(
                0.0, (self.as_of - c.authored_at).total_seconds() / 86400.0
            )
            commit_weight = math.exp(-self.weights.decay_lambda * days_since_commit)

            for f in c.files:
                key = (f.path, c.author_email)
                agg = aggs.get(key)
                if agg is None:
                    agg = _Agg(file=f.path, email=c.author_email)
                    aggs[key] = agg
                agg.commit_count += 1
                agg.additions += f.additions
                agg.deletions += f.deletions
                agg.weighted_count += commit_weight
                agg.weighted_volume += (f.additions + f.deletions) * commit_weight
                if agg.last_authored_at is None or c.authored_at > agg.last_authored_at:
                    agg.last_authored_at = c.authored_at
                    agg.last_name = c.author_name

        if review_graph is not None:
            for (path, email), agg in aggs.items():
                login = _login_from_email(email)
                if login:
                    agg.review_score = review_graph.score_for(login, path)

        commit_w, volume_w, recency_w, review_w = self._active_weights()

        unnormalized: list[FileOwnership] = []
        for (path, email), agg in aggs.items():
            assert agg.last_authored_at is not None
            days_since = max(0.0, (self.as_of - agg.last_authored_at).total_seconds() / 86400.0)
            max_recency = math.exp(-self.weights.decay_lambda * days_since)

            raw = (
                agg.weighted_count * commit_w
                + math.log(agg.weighted_volume + 1) * volume_w
                + max_recency * recency_w
                + agg.review_score * review_w
            )

            unnormalized.append(
                FileOwnership(
                    file=path,
                    author_email=email,
                    commit_count=agg.commit_count,
                    additions=agg.additions,
                    deletions=agg.deletions,
                    last_authored_at=agg.last_authored_at,
                    days_since_last=days_since,
                    raw_score=raw,
                    coverage=0.0,
                )
            )

        sums_by_file: dict[str, float] = {}
        for s in unnormalized:
            sums_by_file[s.file] = sums_by_file.get(s.file, 0.0) + s.raw_score

        normalized = tuple(
            replace(
                s,
                coverage=(s.raw_score / sums_by_file[s.file]) if sums_by_file[s.file] > 0 else 0.0,
            )
            for s in unnormalized
        )
        names = {email: name for email, (name, _) in names_by_email.items()}
        return OwnershipMap(scores=normalized, names=names)

    def _active_weights(self) -> tuple[float, float, float, float]:
        w = self.weights
        return (w.commit, w.volume, w.recency, w.review)


def _login_from_email(email: str) -> str | None:
    """Recover a GitHub login from a canonicalised email.

    The collector normalises `XXX+login@users.noreply.github.com` to
    `login@github`. Real corporate emails can not be resolved without
    extra mapping, so we return None and let the caller skip.
    """
    if email.endswith("@github"):
        return email[: -len("@github")]
    return None
