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

Sections appear in this order. Several are conditional on flags — those
are marked.

### Executive summary *(only with `--with-narrative`)*
An LLM-written headline action plus a 2–3 paragraph summary, with
per-recommendation rationales spliced into the recommendations table.
A draft to discuss with the team, not a directive. Feeds: the
[narrative engine](algorithms.md), which reads the same `ReportContext`
everything else is built from.

### Engineering Resilience Score
The headline 0–100 number, its band, and the four sub-scores
(ownership / decay / review / activity). Sub-scores with no data show
"no data" and are excluded from the average — they are not counted as
zero. **Read it as:** the one number to track over time; the
sub-scores tell you *which* dimension is dragging. Feeds:
[resilience score](algorithms.md#13-resilience-score).

### Departure scenarios *(only when `--simulate-top-departures` > 0)*
A card per top-N contributor: files affected, files that would become
orphans, average coverage loss, and the most-affected services. **Read
it as:** the concrete cost of losing each of your biggest knowledge
holders. Feeds: [departure simulation](algorithms.md#4-departure-simulation).

### Central models — structural types other code is bound to *(needs the dependency graph; Python files only)*
Files that define data-model classes (`@dataclass`, pydantic
`BaseModel`, attrs, msgspec `Struct`, `TypedDict`, …) ranked by how many
other files import them. **Read it as:** breaking changes to a
high-dependents model ripple widely; single-owner concentration on one
of these is a louder warning than on ordinary code. Feeds:
[language extractors](algorithms.md#6-language-extractors) +
[module aggregation](algorithms.md#8-module-aggregation).

### Structural backbone — top central files *(needs the dependency graph)*
The top files by PageRank importance, with dependents count and top
owner. **Read it as:** these are the files everything else
(transitively) depends on — weak ownership or decay here matters most.
Feeds: [PageRank importance](algorithms.md#7-pagerank-importance).

### Module dependency map *(needs the dependency graph)*
A Mermaid diagram of the repo's architecture at the module level —
top-K modules, inter-module edges weighted by dependency count. **Read
it as:** the shape of the system; thick edges are tight coupling.
Feeds: [module aggregation](algorithms.md#8-module-aggregation).

### Resilience trend *(only with `--with-trend`)*
The resilience score recomputed at 90/60/30/0 days ago, plus the delta.
Only ownership + decay sub-scores are computed historically. **Read it
as:** is the repo getting more or less resilient? Feeds:
[trend engine](algorithms.md#16-trend-engine).

### Activity summary
Headline counts for the window: commits, unique authors, files touched,
lines added/deleted. Context, not risk. Feeds: the git collector.

### Service risk map
Bus factor per service (top-level directory): file count, bus factor,
risk level, top owners. **Read it as:** which whole areas of the
codebase rest on too few people. Feeds:
[bus factor](algorithms.md#2-bus-factor).

### Files with single ownership
The `critical` (bus factor 1) files, filtered to real code and — when
the dependency graph ran — to files above the importance threshold.
**Read it as:** the specific single-points-of-failure worth acting on.
Feeds: [bus factor](algorithms.md#2-bus-factor).

### Review lineage *(only with `--with-reviews`)*
Two sub-tables:
- **Files with highest rubber-stamp ratio** — where approvals land
  without a substantive comment.
- **Files with lowest reviewer diversity** — where one reviewer carries
  most of the review load (low HHI).

**Read it as:** where "code review" is happening on paper but not in
substance. Feeds: [review graph](algorithms.md#9-review-graph).

### CODEOWNERS validation *(only with `--check-codeowners` and a `CODEOWNERS` file)*
Counts of aligned / mismatch / stale / orphan / team-only files, then
sub-tables for:
- **Mismatches** — declared owner is not the actual top contributor.
- **Stale entries** — declared owner hasn't touched the file recently.
- **Orphans** — files with no CODEOWNERS rule.

**Read it as:** where your declared ownership has drifted from reality.
Feeds: [CODEOWNERS validation](algorithms.md#17-codeowners-validation).

### Recommended actions
The prioritised action list — priority, category, title, description,
target, evidence, and a fragility-pattern badge where one applies
(`review-without-scrutiny`, `single-owner-concentration`,
`velocity-without-review`). **Read it as:** the punch list; sorted so
the top of the table is where to start. Feeds:
[recommendation engine](algorithms.md#14-recommendation-engine).

### Author signal profiles — experimental *(only with `--experimental-ai-signal`)*
Per-author profile type (`Real Growth` / `AI Amplified Healthy` /
`Fake Velocity` / `Bot` / `Insufficient Data`), signal strength,
evidence weight, and a plain-text explanation. **Read it as:** *whose
recent activity shape is worth a closer look* — explicitly not a
verdict on AI authorship or performance. Feeds:
[AI detector](algorithms.md#10-ai-amplification-detector) +
[quality signal](algorithms.md#11-quality-signal) +
[profile classifier](algorithms.md#12-author-profile-classifier).

### PR activity mix *(only with `--with-reviews`)*
The breakdown of PRs by category (feature / refactor / cleanup / test /
docs / chore) and a **Top churned files** sub-table. **Read it as:** how
much of the throughput is real feature work vs noise, and which files
churn the most. Feeds: [diff classifier](algorithms.md#15-diff-classifier).

### Knowledge decay — top concerns
The files with the highest decay score: top owner, days since they last
touched it, lines changed by others since, and the 30/60/90-day
projection. **Read it as:** files whose knowledge is going stale on a
predictable trajectory. Feeds:
[knowledge decay](algorithms.md#3-knowledge-decay).

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
