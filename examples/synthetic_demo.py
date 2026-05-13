"""
Build a realistic synthetic repository and run blindspot on it.

Run:
    python examples/synthetic_demo.py

Produces:
    demo_report.html in the current directory.

Designed risk patterns
----------------------
1. payment/billing.py        - Bob is the only person who ever touched it (bus factor 1).
2. payment/refund.py         - Eve dominant historically but absent ~70 days; others touched it after.
3. shared/utils.py           - Healthy distribution: Alice, Carol, Dave all contribute.
4. auth/legacy.py            - Alice's single ownership, last touched ~150 days ago (decay risk).
5. auth/oauth.py             - Carol dominant, recent activity (healthy single-owner-ish).
6. payment/checkout.py       - Bob + Dave; Bob dominant but Dave is growing.
7. payment/discount.py       - Frank shows 'Fake Velocity' pattern: stable baseline, then
                                sudden 10x commit frequency, huge blocks, bug-fix-heavy
                                messages, zero tests. Triggers --experimental-ai-signal.
"""

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from git import Actor, Repo

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))


@dataclass
class C:
    days_ago: int
    author: str
    email: str
    file: str
    content: str
    msg: str = "update"


PEOPLE = {
    "alice": ("Alice", "alice@example.com"),
    "bob": ("Bob", "bob@example.com"),
    "carol": ("Carol", "carol@example.com"),
    "dave": ("Dave", "dave@example.com"),
    "eve": ("Eve", "eve@example.com"),
    "frank": ("Frank", "frank@example.com"),
}


def _commits() -> list[C]:
    out: list[C] = []

    def lines(n: int) -> str:
        return "\n".join(f"line {i}" for i in range(n)) + "\n"

    # payment/billing.py — Bob is the only contributor (bus factor = 1)
    for days, n in [(170, 30), (150, 60), (120, 100), (80, 140), (40, 160), (10, 180)]:
        out.append(C(days, *PEOPLE["bob"], "payment/billing.py", lines(n), "billing update"))

    # payment/refund.py — Eve dominant historically, absent now, others changed after
    for days, n in [(180, 50), (160, 120), (130, 200), (90, 250)]:
        out.append(C(days, *PEOPLE["eve"], "payment/refund.py", lines(n), "refund core"))
    out.append(C(60, *PEOPLE["dave"], "payment/refund.py", lines(280), "small refund tweak"))
    out.append(C(30, *PEOPLE["alice"], "payment/refund.py", lines(310), "refund safety net"))
    out.append(C(5, *PEOPLE["bob"], "payment/refund.py", lines(340), "refund hotfix"))

    # payment/checkout.py — Bob dominant, Dave growing
    for days, n in [(160, 40), (130, 90), (100, 130), (60, 170)]:
        out.append(C(days, *PEOPLE["bob"], "payment/checkout.py", lines(n), "checkout"))
    for days, n in [(45, 180), (20, 200), (3, 220)]:
        out.append(C(days, *PEOPLE["dave"], "payment/checkout.py", lines(n), "checkout"))

    # auth/legacy.py — Alice only, ancient
    out.append(C(170, *PEOPLE["alice"], "auth/legacy.py", lines(80), "legacy auth"))
    out.append(C(150, *PEOPLE["alice"], "auth/legacy.py", lines(120), "legacy fixes"))

    # auth/oauth.py — Carol dominant, recent
    for days, n in [(140, 60), (110, 100), (70, 140), (30, 170), (5, 195)]:
        out.append(C(days, *PEOPLE["carol"], "auth/oauth.py", lines(n), "oauth"))
    out.append(C(40, *PEOPLE["dave"], "auth/oauth.py", lines(180), "oauth helper"))

    # auth/session.py — Carol + Frank balanced
    for days, n in [(150, 30), (110, 70), (60, 110), (15, 150)]:
        author = "carol" if days % 2 == 0 else "frank"
        out.append(C(days, *PEOPLE[author], "auth/session.py", lines(n), "session"))

    # shared/utils.py — healthy: Alice + Carol + Dave
    for days, who, n in [
        (175, "alice", 20),
        (160, "carol", 35),
        (140, "dave", 50),
        (120, "alice", 65),
        (95, "carol", 80),
        (70, "dave", 95),
        (45, "alice", 110),
        (20, "carol", 125),
        (3, "dave", 140),
    ]:
        out.append(C(days, *PEOPLE[who], "shared/utils.py", lines(n), "utils"))

    # shared/logger.py — Alice dominant but Frank reviews-touch
    for days, who, n in [(165, "alice", 25), (130, "alice", 55), (90, "frank", 65), (40, "alice", 90), (10, "alice", 110)]:
        out.append(C(days, *PEOPLE[who], "shared/logger.py", lines(n), "logger"))

    # payment/discount.py — Frank's Fake Velocity pattern.
    # Baseline: small, infrequent, descriptive commits.
    for days, n, msg in [
        (340, 30, "tidy"),
        (300, 35, "rename helper"),
        (260, 40, "address review feedback"),
        (200, 50, "small tweak"),
    ]:
        out.append(C(days, *PEOPLE["frank"], "payment/discount.py", lines(n), msg))
    # Last 60 days: explosion of large, bug-fix-heavy, off-hours commits with no tests.
    for i in range(18):
        days_ago = 60 - i * 3
        out.append(
            C(
                days_ago,
                *PEOPLE["frank"],
                "payment/discount.py",
                lines(60 + i * 35),
                "fix bug in discount logic and add comprehensive validation hotfix",
            )
        )

    # README.md — Alice and Bob both touch it
    out.append(C(180, *PEOPLE["alice"], "README.md", "blindspot demo\n", "init"))
    out.append(C(90, *PEOPLE["bob"], "README.md", "blindspot demo\nupdated\n", "doc"))
    out.append(C(10, *PEOPLE["alice"], "README.md", "blindspot demo\nupdated\nv2\n", "doc"))

    return out


CODEOWNERS_CONTENT = """\
# Synthetic CODEOWNERS for demo — mix of accurate, stale, and mismatched entries.
payment/billing.py    @bob
payment/checkout.py   @alice
payment/discount.py   @frank
payment/refund.py     @eve
auth/legacy.py        @alice
auth/oauth.py         @carol
auth/session.py       @org/auth-team
shared/utils.py       @alice @carol @dave
# shared/logger.py intentionally missing → orphan
"""


def build_repo(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    target = target.resolve()
    repo = Repo.init(target)
    with repo.config_writer() as cw:
        cw.set_value("user", "email", "demo@example.com")
        cw.set_value("user", "name", "Demo")
        cw.set_value("commit", "gpgsign", "false")

    now = datetime.now(UTC)
    commits = sorted(_commits(), key=lambda c: -c.days_ago)
    # Write CODEOWNERS once at the start (Alice's first commit).
    (target / ".github").mkdir(parents=True, exist_ok=True)
    (target / ".github" / "CODEOWNERS").write_text(CODEOWNERS_CONTENT)
    repo.index.add([str(target / ".github" / "CODEOWNERS")])
    init_dt = (now - timedelta(days=200)).replace(microsecond=0)
    init_date = f"{int(init_dt.timestamp())} +0000"
    actor0 = Actor("Alice", "alice@example.com")
    repo.index.commit(
        message="add CODEOWNERS",
        author=actor0, committer=actor0,
        author_date=init_date, commit_date=init_date,
    )
    for c in commits:
        fpath = target / c.file
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(c.content)
        repo.index.add([str(fpath)])
        actor = Actor(c.author, c.email)
        ts = (now - timedelta(days=c.days_ago)).replace(microsecond=0)
        date = f"{int(ts.timestamp())} +0000"
        repo.index.commit(message=c.msg, author=actor, committer=actor, author_date=date, commit_date=date)


def main() -> None:
    output_html = REPO_ROOT / "demo_report.html"
    workdir = Path(tempfile.mkdtemp(prefix="blindspot_demo_"))
    repo_path = workdir / "demo_repo"
    try:
        build_repo(repo_path)
        print(f"Built synthetic repo at {repo_path}")
        subprocess.run(
            [
                str(REPO_ROOT / ".venv/bin/blindspot"),
                "scan",
                str(repo_path),
                "--since-days",
                "365",
                "--experimental-ai-signal",
                "--with-trend",
                "--output",
                str(output_html),
            ],
            check=True,
        )
        print(f"\n→ Open the report: {output_html}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    main()
