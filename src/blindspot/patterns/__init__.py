"""Pattern detectors — composite signal recognition.

A "pattern" combines two or more single-metric signals into a named
organisational shape that no single metric catches alone. The asset
that no single-metric competitor can copy without first carrying all
the underlying signals.

This package is the home for those detectors. Each pattern returns a
``PatternHit`` (or empty tuple) — never raises. The set of hits drives
both the "Patterns detected" report section and the executive-brief
pattern count line.
"""

from blindspot.patterns.models import PatternHit, PatternSeverity
from blindspot.patterns.fragile_velocity import detect_fragile_velocity
from blindspot.patterns.engine import detect_all_patterns

__all__ = [
    "PatternHit",
    "PatternSeverity",
    "detect_all_patterns",
    "detect_fragile_velocity",
]
