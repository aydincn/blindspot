from datetime import UTC, datetime

from blindspot.collector import GitCollector
from blindspot.ownership import OwnershipEngine
from blindspot.risk_models import KnowledgeDecayEngine

from tests.conftest import CommitSpec


def _setup(repo, *, as_of: datetime | None = None):
    commits = list(GitCollector(repo, since_days=365).collect())
    ownership = OwnershipEngine(as_of=as_of).compute(commits)
    return commits, ownership


def test_active_owner_has_low_decay(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "f.py", "1\n", 5),
            CommitSpec("Alice", "alice@x.com", "f.py", "1\n2\n", 4),
            CommitSpec("Alice", "alice@x.com", "f.py", "1\n2\n3\n", 1),
        ]
    )
    commits, ownership = _setup(repo)
    decays = KnowledgeDecayEngine().for_files(commits, ownership)

    assert len(decays) == 1
    assert decays[0].top_owner == "alice@x.com"
    assert decays[0].risk_level in ("low", "medium")
    assert decays[0].lines_changed_after == 0


def test_absent_owner_with_churn_after_them_raises_decay(make_repo):
    # Alice has many recent-enough commits to remain dominant owner, but stopped
    # touching the file 90+ days ago. Bob's smaller recent change still adds churn.
    alice_commits = [
        CommitSpec("Alice", "alice@x.com", "f.py", f"alice {i}\n" * (i + 1), days_ago)
        for i, days_ago in enumerate(range(95, 200, 10))
    ]
    bob_commits = [
        CommitSpec(
            "Bob", "bob@x.com", "f.py",
            ("alice 0\n" * 5) + "bob\n" * 30,
            30,
        ),
    ]
    repo = make_repo(alice_commits + bob_commits)
    commits, ownership = _setup(repo)
    decays = KnowledgeDecayEngine().for_files(commits, ownership)

    fd = decays[0]
    assert fd.top_owner == "alice@x.com"
    assert fd.days_since_owner_touch >= 90
    assert fd.lines_changed_after > 0
    assert fd.volatility > 0
    assert fd.person_absence > 0.5
    assert fd.decay_score > 0.4


def test_projections_increase_with_time(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "f.py", "x\n", 100),
            CommitSpec("Bob", "bob@x.com", "f.py", "x\ny\n", 50),
        ]
    )
    commits, ownership = _setup(repo)
    decays = KnowledgeDecayEngine().for_files(commits, ownership)

    fd = decays[0]
    assert fd.projections[30] >= fd.decay_score
    assert fd.projections[60] >= fd.projections[30]
    assert fd.projections[90] >= fd.projections[60]


def test_service_aggregation(make_repo):
    repo = make_repo(
        [
            CommitSpec("Alice", "alice@x.com", "payment/a.py", "1\n", 200),
            CommitSpec("Alice", "alice@x.com", "payment/b.py", "1\n", 5),
            CommitSpec("Alice", "alice@x.com", "shared/x.py", "1\n", 5),
        ]
    )
    commits, ownership = _setup(repo)
    services = KnowledgeDecayEngine().for_services(commits, ownership)

    payment = next(s for s in services if s.service == "payment")
    shared = next(s for s in services if s.service == "shared")
    assert payment.avg_decay_score > shared.avg_decay_score
    assert payment.file_count == 2
