from datetime import UTC, datetime

from blindspot.ownership.models import FileOwnership, OwnershipMap
from blindspot.resilience.knowledge_graph import build_knowledge_graph


def _score(file: str, email: str, cov: float) -> FileOwnership:
    return FileOwnership(
        file=file, author_email=email, commit_count=1,
        additions=10, deletions=2,
        last_authored_at=datetime.now(UTC), days_since_last=10.0,
        raw_score=0.5, coverage=cov,
    )


def _om(*scores: FileOwnership) -> OwnershipMap:
    return OwnershipMap(scores=tuple(scores), names={})


def test_builds_bipartite_edges_for_dominant_pair():
    om = _om(
        _score("payment/a.py", "alice@x.com", 0.9),
        _score("payment/b.py", "alice@x.com", 0.9),
        _score("auth/c.py", "bob@x.com", 0.95),
    )
    g = build_knowledge_graph(om)
    pairs = {(e.contributor, e.service) for e in g.edges}
    assert ("alice@x.com", "payment") in pairs
    assert ("bob@x.com", "auth") in pairs


def test_drops_edges_below_min_coverage():
    om = _om(
        _score("payment/a.py", "alice@x.com", 0.9),  # 90% of 1 file
        _score("payment/b.py", "alice@x.com", 0.05),
        _score("payment/c.py", "bob@x.com", 0.05),  # too low
    )
    g = build_knowledge_graph(om, min_edge_coverage=0.20)
    pairs = {(e.contributor, e.service) for e in g.edges}
    assert ("alice@x.com", "payment") in pairs
    assert ("bob@x.com", "payment") not in pairs


def test_caps_top_contributors_and_services():
    om = _om(
        *[_score(f"svc{i}/a.py", f"u{i}@x.com", 0.9) for i in range(10)]
    )
    g = build_knowledge_graph(om, top_contributors=3, top_services=2)
    assert len(g.contributors) == 3
    assert len(g.services) == 2


def test_empty_ownership_produces_empty_graph():
    g = build_knowledge_graph(_om())
    assert g.contributors == ()
    assert g.services == ()
    assert g.edges == ()
