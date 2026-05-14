# Glossary

One-line definitions for every term Blindspot uses. For the full
algorithm behind a term, follow the link into
[algorithms.md](algorithms.md).

**Coverage** — a contributor's normalised share of the "effective
knowledge" of a file, weighted by commit recency, volume, and review
activity; sums to 1.0 across a file's contributors.
[→](algorithms.md#1-ownership--coverage-scoring)

**Ownership map** — the full set of per-file, per-contributor coverage
scores produced for a repo; the input to bus factor, decay, departure,
and CODEOWNERS validation.

**Bus factor** — the minimum number of top contributors whose combined
coverage reaches 80% of a file or service; bus factor 1 = single point
of failure. [→](algorithms.md#2-bus-factor)

**Service** — the top-level directory of a path, used as the unit for
service-level rollups. Special buckets: `(root)`, `(config)`, `(other)`.

**Risk level** — the qualitative band for a bus factor or decay score:
`critical` / `high` / `medium` / `healthy` (or `low` for decay).

**Knowledge decay** — a 0–1 score for how stale a file's knowledge is
becoming: its owner stopped touching it *and* others keep changing it.
[→](algorithms.md#3-knowledge-decay)

**Volatility** — the component of decay driven by how many lines others
changed after the owner's last touch.

**Person-absence** — the component of decay driven by how long the
owner has been away from the file.

**Decay projection** — the decay score re-evaluated 30/60/90 days into
the future, holding volatility constant.

**Departure scenario** — a simulation of one or more named people
leaving: per-file coverage loss, orphaned files, per-service impact.
[→](algorithms.md#4-departure-simulation)

**Orphan file** — a file where, after a simulated departure, no
remaining contributor holds at least 30% coverage.

**Coverage loss** — the total coverage held by the departing people on
a given file.

**Remaining-owner gap** — a ranked "potential successor": a person who
would inherit orphaned files as their new top owner.

**Dependency graph** — the directed graph of file→file imports in the
repo, the basis for structural-importance ranking.
[→](algorithms.md#5-dependency-graph-build)

**Code root** — the subtree the dependency graph is built from;
auto-detected as `src/` → `lib/` → `app/` → repo root, overridable with
`--code-root`.

**Importance / PageRank** — a file's structural importance: how much
other files (transitively) depend on it.
[→](algorithms.md#7-pagerank-importance)

**Central file** — a file ranked among the highest by PageRank
importance — part of the codebase's structural backbone.

**Central model** — a file defining data-model classes (`@dataclass`,
pydantic `BaseModel`, attrs, `TypedDict`, …) that many other files
import. [→](algorithms.md#6-language-extractors)

**Module map** — the dependency graph rolled up to the directory-module
level for a readable architecture diagram.
[→](algorithms.md#8-module-aggregation)

**Review graph** — per-file review-hygiene statistics derived from PR
data. [→](algorithms.md#9-review-graph)

**Rubber-stamp ratio** — the share of a file's approvals that came with
no substantive review comment; high = stamp-without-reading.

**Reviewer diversity (HHI)** — `1 − Σ share²` over a file's reviewers; a
Herfindahl index, inverted. 1.0 = review load perfectly spread, 0.0 =
one reviewer carries everything.

**Approval latency** — the median time from a PR being opened to its
first approval; very low values suggest review too fast to be real.

**AI amplification** — an experimental, behavioural signal: an author's
recent activity shape shifted sharply versus *their own* baseline. It
detects an activity-shape change, **not** AI authorship.
[→](algorithms.md#10-ai-amplification-detector)

**Quality signal** — an experimental 0–1 code-quality risk score for an
author's recent work (rework, bug-fixing, reverts, rejected reviews,
missing tests, thin PR descriptions).
[→](algorithms.md#11-quality-signal)

**Author profile** — the classification combining AI + quality signals:
`Real Growth` / `AI Amplified Healthy` / `Fake Velocity` / `Bot` /
`Insufficient Data`. [→](algorithms.md#12-author-profile-classifier)

**Evidence weight** — a `[0.6, 1.0]` confidence multiplier on an
author's activity signal; lower means "trust this signal less", never a
penalty.

**Fake velocity** — an author profile where output spiked *and*
code-quality risk rose — worth a closer look, not a verdict.

**Resilience score** — the composite 0–100 number synthesised from the
ownership, decay, review, and activity sub-scores.
[→](algorithms.md#13-resilience-score)

**Resilience band** — the qualitative band for the overall score:
`Strong` (≥80) / `Moderate` (≥60) / `Fragile` (≥40) / `Critical` (<40).

**Sub-score** — one of the four resilience inputs (ownership / decay /
review / activity), each 0–100; missing ones are excluded from the
average, not zeroed.

**Trend** — the resilience score recomputed at past points in time
(90/60/30/0 days ago). [→](algorithms.md#16-trend-engine)

**Recommendation** — one prioritised, evidence-backed action emitted by
the recommendation engine. [→](algorithms.md#14-recommendation-engine)

**Fragility pattern** — a named AI-era failure mode tagged on
recommendations: `review-without-scrutiny`,
`single-owner-concentration`, or `velocity-without-review`.

**Importance threshold** — the PageRank floor (default 0.005) below
which a file is dropped from recommendations and display tables, to cut
noise from leaf utilities and one-shot scripts.

**Diff classification** — labelling each file `code` / `test` / `docs` /
`chore` and each PR `feature` / `refactor` / `cleanup` / `test` /
`docs` / `chore`. [→](algorithms.md#15-diff-classifier)

**Churn** — total `additions + deletions` on a file across the analysis
window; the "top churned files" are the most-changed.

**CODEOWNERS validation** — checking a repo's declared `CODEOWNERS`
against actual ownership; each file is `aligned`, `mismatch`, `stale`,
`team_only`, or `orphan`. [→](algorithms.md#17-codeowners-validation)

**Narrative** — the optional LLM-generated executive summary, headline
action, and per-recommendation rationales layered on top of the report.

**Provider** — a hosting service Blindspot can pull review data from:
GitHub or Bitbucket Cloud.

**`.blindspot.yaml`** — the optional config file holding LLM, GitHub,
and Bitbucket credentials; resolved CLI flag → CWD → scanned-repo →
user config. Never read from environment variables.
[→](configuration.md)
