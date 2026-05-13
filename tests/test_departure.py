from blindspot.collector import GitCollector
from blindspot.ownership import OwnershipEngine
from blindspot.risk_models import DepartureSimulation

from tests.conftest import CommitSpec


def _ownership(repo):
    commits = list(GitCollector(repo, since_days=365).collect())
    return OwnershipEngine().compute(commits)


def test_departure_of_sole_owner_orphans_file(make_repo):
    repo = make_repo([CommitSpec("Solo", "solo@x.com", "x.py", "1\n", 5)])
    om = _ownership(repo)
    report = DepartureSimulation().simulate(om, ["solo@x.com"])

    assert report.orphaned_files == 1
    assert report.files[0].becomes_orphan
    assert report.files[0].remaining_top_owner is None
    assert report.files[0].severity == "critical"


def test_departure_with_backup_owner_does_not_orphan(make_repo):
    repo = make_repo(
        [
            CommitSpec("A", "a@x.com", "x.py", "1\n", 5),
            CommitSpec("B", "b@x.com", "x.py", "1\n2\n", 4),
            CommitSpec("A", "a@x.com", "x.py", "1\n2\n3\n", 3),
            CommitSpec("B", "b@x.com", "x.py", "1\n2\n3\n4\n", 2),
        ]
    )
    om = _ownership(repo)
    report = DepartureSimulation().simulate(om, ["a@x.com"])

    fi = report.files[0]
    assert not fi.becomes_orphan
    assert fi.remaining_top_owner == "b@x.com"
    assert fi.remaining_top_coverage > 0.30


def test_multiple_departures_aggregate(make_repo):
    repo = make_repo(
        [
            CommitSpec("A", "a@x.com", "f1.py", "1\n", 5),
            CommitSpec("B", "b@x.com", "f2.py", "1\n", 4),
            CommitSpec("C", "c@x.com", "f3.py", "1\n", 3),
        ]
    )
    om = _ownership(repo)
    report = DepartureSimulation().simulate(om, ["a@x.com", "b@x.com"])

    assert report.orphaned_files == 2
    assert report.affected_files == 2


def test_service_aggregation(make_repo):
    repo = make_repo(
        [
            CommitSpec("A", "a@x.com", "payment/x.py", "1\n", 5),
            CommitSpec("A", "a@x.com", "payment/y.py", "1\n", 4),
            CommitSpec("B", "b@x.com", "shared/z.py", "1\n", 3),
            CommitSpec("C", "c@x.com", "shared/z.py", "1\n2\n", 2),
        ]
    )
    om = _ownership(repo)
    report = DepartureSimulation().simulate(om, ["a@x.com"])

    payment = next(s for s in report.services if s.service == "payment")
    shared = next(s for s in report.services if s.service == "shared")

    assert payment.orphaned_files == 2
    assert payment.severity == "critical"
    assert shared.orphaned_files == 0


def test_departing_email_normalised_to_lowercase(make_repo):
    repo = make_repo([CommitSpec("Solo", "solo@x.com", "x.py", "1\n", 5)])
    om = _ownership(repo)
    report = DepartureSimulation().simulate(om, ["SOLO@X.COM"])

    assert report.orphaned_files == 1
