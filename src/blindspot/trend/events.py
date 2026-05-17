"""Timeline events — let the user pin organisational events (layoffs,
re-orgs, AI rollouts) to the resilience trend.

Events are read from a top-level ``events:`` block in
``.blindspot.yaml``::

    events:
      - {date: "2026-03-15", label: "AI rollout"}
      - {date: "2026-04-01", label: "Q1 layoffs"}
      - {date: "2026-05-01", label: "Platform reorg"}

The trend table then attaches the nearest event to each snapshot, so a
reader can see at a glance whether a drop coincided with a known
organisational change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    date: date
    label: str


def load_events(repo_path: Path) -> tuple[TimelineEvent, ...]:
    """Parse ``events:`` from ``.blindspot.yaml`` at the repo root. Returns
    an empty tuple if the file or block is missing."""
    yaml_path = repo_path / ".blindspot.yaml"
    if not yaml_path.exists():
        return ()
    try:
        data = yaml.safe_load(yaml_path.read_text()) or {}
    except yaml.YAMLError:
        return ()
    raw = data.get("events") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return ()
    out: list[TimelineEvent] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        d = entry.get("date")
        label = entry.get("label", "")
        if not d or not label:
            continue
        if isinstance(d, str):
            try:
                d = datetime.strptime(d, "%Y-%m-%d").date()
            except ValueError:
                continue
        elif isinstance(d, datetime):
            d = d.date()
        elif not isinstance(d, date):
            continue
        out.append(TimelineEvent(date=d, label=str(label)))
    out.sort(key=lambda e: e.date)
    return tuple(out)


def event_for_snapshot(
    snapshot_date: date,
    events: tuple[TimelineEvent, ...],
    *,
    window_days: int = 14,
) -> TimelineEvent | None:
    """Return the event whose date is within ``window_days`` of the
    snapshot, picking the closest one. ``None`` if no event qualifies."""
    if not events:
        return None
    best: tuple[int, TimelineEvent] | None = None
    for e in events:
        delta = abs((snapshot_date - e.date).days)
        if delta > window_days:
            continue
        if best is None or delta < best[0]:
            best = (delta, e)
    return best[1] if best else None


__all__ = ["TimelineEvent", "event_for_snapshot", "load_events"]
