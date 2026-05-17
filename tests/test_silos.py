from blindspot.resilience.silos import detect_silos
from blindspot.review_graph.engine import ReviewGraph


def _rg(*entries: tuple[str, str, float]) -> ReviewGraph:
    return ReviewGraph(
        by_reviewer_file={(r, f): s for r, f, s in entries},
        file_stats={},
    )


def test_no_silos_when_reviewers_overlap_across_services():
    rg = _rg(
        ("alice", "api/a.py", 0.8), ("alice", "api/b.py", 0.8),
        ("alice", "api/c.py", 0.8), ("alice", "api/d.py", 0.8),
        ("alice", "api/e.py", 0.8),
        ("bob", "auth/x.py", 0.7), ("bob", "auth/y.py", 0.7),
        ("bob", "auth/z.py", 0.7), ("bob", "auth/w.py", 0.7),
        ("bob", "auth/v.py", 0.7),
        # cross-service reviewer
        ("alice", "auth/x.py", 0.5),
    )
    report = detect_silos(rg)
    assert report.findings == ()


def test_flags_silos_when_reviewer_sets_disjoint():
    rg = _rg(
        # api: only alice + bob, never appear elsewhere
        ("alice", "api/a.py", 0.8), ("alice", "api/b.py", 0.8),
        ("alice", "api/c.py", 0.8), ("bob", "api/d.py", 0.8),
        ("bob", "api/e.py", 0.8),
        # auth: only carol + dave
        ("carol", "auth/x.py", 0.7), ("carol", "auth/y.py", 0.7),
        ("carol", "auth/z.py", 0.7), ("dave", "auth/w.py", 0.7),
        ("dave", "auth/v.py", 0.7),
    )
    report = detect_silos(rg)
    services = {f.service for f in report.findings}
    assert "api" in services
    assert "auth" in services


def test_drops_low_volume_services():
    rg = _rg(
        # api: only 2 reviews — below threshold
        ("alice", "api/a.py", 0.8), ("alice", "api/b.py", 0.8),
        # auth: enough volume + reviewers
        ("carol", "auth/x.py", 0.7), ("carol", "auth/y.py", 0.7),
        ("carol", "auth/z.py", 0.7), ("dave", "auth/w.py", 0.7),
        ("dave", "auth/v.py", 0.7),
    )
    report = detect_silos(rg)
    # Both can't be flagged because there's effectively only one eligible
    # service after filtering — silo detection needs ≥ 2 to compare.
    assert report.findings == ()


def test_empty_review_graph_no_silos():
    report = detect_silos(ReviewGraph())
    assert report.findings == ()
