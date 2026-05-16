# Outputs — How to Read the Results

Blindspot produces a single self-contained HTML file. This page explains
every section: **what it shows**, **how to read it**, and **which
algorithm feeds it** (linked to [algorithms.md](algorithms.md)).

There are two report shapes:
- the **scan report** (`blindspot scan`) — full repo health
- the **departure report** (`blindspot simulate`) — focused
  "what if X leaves"

---

## Shared labels

The same severity vocabulary is used everywhere, so learn it once.

**Risk levels** (bus factor, decay):

| Label | Meaning |
|---|---|
| `critical` | Single point of failure / knowledge already badly stale |
| `high` | Two-person dependency / decay above 0.50 |
| `medium` | Three-person dependency / decay above 0.25 |
| `healthy` / `low` | Resilient |

**Resilience bands** (overall score):

| Band | Score | Meaning |
|---|---|---|
| `Strong` | ≥ 80 | Knowledge is well distributed and fresh |
| `Moderate` | ≥ 60 | Some thin spots; manageable |
| `Fragile` | ≥ 40 | Real concentration / decay risk |
| `Critical` | < 40 | Knowledge is dangerously concentrated or stale |

**Departure severity** (per file):

| Label | Meaning |
|---|---|
| `critical` | File becomes an orphan — no strong remaining owner |
| `high` | Loses > 70% of its coverage |
| `medium` | Loses > 40% of its coverage |
| `low` | Minor impact |

---

## The scan report

Starting in 0.0.5a, the report is organised under four group headers so
you can scan it top-to-bottom in order of CTO-relevance: **TL;DR**,
**People & Ownership**, **Knowledge State**, **Process Quality**, with
an optional collapsible **Architecture details** block at the bottom.

Sections appear in this order. Several are conditional on flags or
data availability — those are marked.

### (Top) Executive summary *(narrative engine, always rendered)*
An LLM-written or rule-based headline action plus a 2–3 paragraph
summary, with per-recommendation rationales spliced into the
recommendations table below. A draft to discuss with the team, not a
directive. The risk-inventory paragraph names counts for: services on a
single contributor, files in critical decay, files that would orphan in
the worst departure scenario, rubber-stamp files, high-correction-load
files, and services lacking AI-readable operational context. Feeds: the
[narrative engine](algorithms.md), which reads the same `ReportContext`
everything else is built from.

### TL;DR group

#### Engineering Resilience Score
The headline 0–100 number, its band (Strong / Moderate / Fragile /
Critical), a letter grade (A–F) badge next to the overall number, and
the three sub-scores (ownership / decay / review) each with their own
letter grade. Sub-scores with no data show "no data" and are excluded
from the average. **Read it as:** the one number to track over time;
the sub-grades tell you *which* dimension is dragging. Feeds:
[resilience score](algorithms.md#12-resilience-score).

#### Recommended actions
The prioritised action list — priority, category, title, description,
target, evidence, and a fragility-pattern badge where one applies
(`review-without-scrutiny`, `single-owner-concentration`,
`fragile-velocity`). **Read it as:** the punch list; sorted so the top
of the table is where to start. Feeds:
[recommendation engine](algorithms.md#13-recommendation-engine).

#### Resilience trend *(only when there is enough history)*
The resilience score recomputed at 90/60/30/0 days ago, plus the delta.
Only ownership + decay sub-scores are computed historically. **Read it
as:** is the repo getting more or less resilient? Feeds:
[trend engine](algorithms.md#16-trend-engine).

### People & Ownership group

#### Service risk map
Bus factor per service (top-level directory): file count, bus factor,
risk level, top owners. **Read it as:** which whole areas of the
codebase rest on too few people. Feeds:
[bus factor](algorithms.md#2-bus-factor).

#### Files with single ownership
The `critical` (bus factor 1) files, filtered to real code and — when
the dependency graph ran — to files above the importance threshold.
**Read it as:** the specific single-points-of-failure worth acting on.
Feeds: [bus factor](algorithms.md#2-bus-factor).

#### Departure scenarios *(only when `--simulate-top-departures` > 0)*
A card per top-N contributor (default 3): files affected, files that
would become orphans, average coverage loss, and the most-affected
services. **Read it as:** the concrete cost of losing each of your
biggest knowledge holders. Feeds:
[departure simulation](algorithms.md#4-departure-simulation).

### Knowledge State group

#### Knowledge decay — top concerns
The files with the highest decay score: top owner, days since they last
touched it, lines changed by others since, and the 30/60/90-day
projection. **Read it as:** files whose knowledge is going stale on a
predictable trajectory. Feeds:
[knowledge decay](algorithms.md#3-knowledge-decay).

#### AI-native operational context
Per-service coverage matrix of AI-readable artifacts: agent rules,
specs, prompts, architecture decisions, skills. Boolean per category;
coverage percentage is the share of categories present. **Read it as:**
how much organizational memory the codebase carries for new humans *and*
AI agents to load. Services below 2/5 coverage emit a
`KNOWLEDGE_TRANSFER` recommendation (priority bumped to MEDIUM when the
service's bus factor is also ≤ 1). Feeds:
[AI readiness](algorithms.md#11-ai-readiness).

### Process Quality group

#### Review lineage *(only with review credentials)*
Two sub-tables:
- **Files with highest rubber-stamp ratio** — where approvals land
  without a substantive comment.
- **Files with lowest reviewer diversity** — where one reviewer carries
  most of the review load (low HHI).

**Read it as:** where "code review" is happening on paper but not in
substance. Feeds: [review graph](algorithms.md#9-review-graph).

#### Correction load
Top files by share of recent commits that are follow-up fixes or
reverts. **Read it as:** work surfaces where shipping pace is being
paid for in stability — fragile velocity. The table targets the file,
not the contributor; a high ratio (≥ 35%) emits a `FRAGILE_VELOCITY`
recommendation. Feeds: [correction load](algorithms.md#10-correction-load).

### Architecture details *(collapsible, default closed)*

#### Module dependency map *(needs the dependency graph)*
A Mermaid diagram of the repo's architecture at the module level —
top-K modules, inter-module edges weighted by dependency count. **Read
it as:** the shape of the system; thick edges are tight coupling.
Feeds: [module aggregation](algorithms.md#8-module-aggregation).

### Sections removed in 0.0.5a / 0.0.5c (BREAKING)
The HTML report dropped these sections because they were either passive
(no action), low-CTO-value, or duplicated cheaper signals. The engines
still compute the data and the recommendation rules still fire — only
the display was dropped.
- **Activity summary** — basic git stats every tool provides.
- **Central models** — niche, low-CTO value; coupling risk is already
  flagged by the bus factor and the importance filter.
- **Structural backbone** — used only as an internal recommendation
  filter.
- **PR activity mix + top churned files** — *Correction load* is the
  stronger, action-generating equivalent.
- **CODEOWNERS validation** *(0.0.5c)* — the mismatched-owner and
  stale-entry findings still produce `CODEOWNERS_UPDATE`
  recommendations; the standalone validation section was redundant
  next to that punch list.

---

## The departure report

Produced by `blindspot simulate`. Focused entirely on the named
people leaving.

### Departure briefing *(only with `--with-narrative`)*
An LLM-written briefing with mitigation steps for the simulated
departure.

### Impact summary
Headline numbers: total files in scope, files affected, files that
become orphans, average coverage loss across the affected set.

### Service impact
Per-service breakdown: files affected, files orphaned, average and max
coverage loss, severity.

### Files becoming orphaned
The `critical`-severity files — they lose their primary expert and no
remaining contributor has strong enough coverage to take over.

### Heavily-impacted files (still owned, barely)
The `high`-severity files — not orphaned, but losing most of their
coverage. The remaining owner will need ramp-up support.

### Potential successors
The people who would inherit the most orphaned files as new top owner —
a ranked starting point for succession planning. Feeds:
`compute_remaining_gaps()`.

---

## CLI console output

During a `scan`, Blindspot also prints progress to the terminal: a
metadata table (window, commits, authors, files, lines), and — as each
optional step runs — a one-line status (review fetch, dependency graph,
trend, narrative). The console output is a running log; the HTML file is
the actual deliverable.

---

## See also

- [algorithms.md](algorithms.md) — how every number above is computed.
- [cli-reference.md](cli-reference.md) — which flag turns on each
  conditional section.
- [glossary.md](glossary.md) — definitions for any unfamiliar term.
