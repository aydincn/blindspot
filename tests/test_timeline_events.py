from datetime import date
from pathlib import Path

from blindspot.trend.events import (
    TimelineEvent,
    event_for_snapshot,
    load_events,
)


def test_loads_events_from_yaml(tmp_path: Path):
    (tmp_path / ".blindspot.yaml").write_text(
        "events:\n"
        '  - {date: "2026-03-15", label: "AI rollout"}\n'
        '  - {date: "2026-04-01", label: "Q1 layoffs"}\n'
    )
    events = load_events(tmp_path)
    assert len(events) == 2
    assert events[0].label == "AI rollout"
    assert events[0].date == date(2026, 3, 15)


def test_load_missing_file_returns_empty(tmp_path: Path):
    assert load_events(tmp_path) == ()


def test_load_skips_malformed_entries(tmp_path: Path):
    (tmp_path / ".blindspot.yaml").write_text(
        "events:\n"
        '  - {date: "not-a-date", label: "bad"}\n'
        '  - {date: "2026-04-01", label: "Q1 layoffs"}\n'
        "  - 42\n"
        '  - {date: "2026-05-01"}\n'  # missing label
    )
    events = load_events(tmp_path)
    assert len(events) == 1
    assert events[0].label == "Q1 layoffs"


def test_event_for_snapshot_picks_closest_within_window():
    events = (
        TimelineEvent(date=date(2026, 3, 15), label="AI rollout"),
        TimelineEvent(date=date(2026, 4, 1), label="Q1 layoffs"),
    )
    # Snapshot on March 18 → AI rollout (3 days away) wins
    assert event_for_snapshot(date(2026, 3, 18), events).label == "AI rollout"
    # Snapshot on April 5 → Q1 layoffs (4 days away)
    assert event_for_snapshot(date(2026, 4, 5), events).label == "Q1 layoffs"


def test_event_for_snapshot_returns_none_outside_window():
    events = (TimelineEvent(date=date(2026, 3, 15), label="AI rollout"),)
    # 30 days later — outside default 14-day window
    assert event_for_snapshot(date(2026, 4, 30), events) is None
