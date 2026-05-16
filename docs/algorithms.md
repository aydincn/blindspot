# Algorithms

Every number Blindspot produces comes from one of the algorithms below.
Each section gives: **what it measures**, the **exact formula(s)**, every
**parameter** with its default and meaning, and the **output type**.
Source file and line references are included so any value can be
re-verified against the code.

All weights and thresholds live in `src/blindspot/config.py` (ownership,
decay) or as dataclass defaults on the engine classes. None of them are
read from environment variables.

---

## Table of contents

1. [Ownership / coverage scoring](#1-ownership--coverage-scoring)
2. [Bus factor](#2-bus-factor)
3. [Knowledge decay](#3-knowledge-decay)
4. [Departure simulation](#4-departure-simulation)
5. [Dependency graph build](#5-dependency-graph-build)
6. [Language extractors (imports, inheritance, models)](#6-language-extractors)
7. [PageRank importance](#7-pagerank-importance)
8. [Module aggregation](#8-module-aggregation)
9. [Review graph](#9-review-graph)
10. [AI amplification detector](#10-ai-amplification-detector)
11. [Quality signal](#11-quality-signal)
12. [Author profile classifier](#12-author-profile-classifier)
13. [Resilience score](#13-resilience-score)
14. [Recommendation engine + fragility patterns](#14-recommendation-engine)
15. [Diff classifier](#15-diff-classifier)
16. [Trend engine](#16-trend-engine)
17. [CODEOWNERS validation](#17-codeowners-validation)

---

## 1. Ownership / coverage scoring

**Measures:** for every file, what share of the "effective knowledge" of
that file each contributor holds — weighted so recent, substantial, and
reviewed work counts more than old drive-by commits.

**Source:** `src/blindspot/ownership/engine.py`,
weights in `src/blindspot/config.py:OwnershipWeights`.

**Formulas.** Per commit, a recency weight decays exponentially with age:

```
commit_weight = exp(-decay_lambda × days_since_commit)
```

For each `(file, author)` pair the engine accumulates:
- `weighted_count` — sum of `commit_weight` over that author's commits to the file
- `weighted_volume` — sum of `(additions + deletions) × commit_weight`
- `last_authored_at` — most recent touch

`max_recency` is the recency weight of the author's *last* touch of the
file. The raw score combines four terms:

```
raw_score = weighted_count        × w_commit      (0.30)
          + log(weighted_volume+1) × w_volume     (0.20)
          + max_recency           × w_recency     (0.35)
          + review_score          × w_review      (0.15)
```

`review_score` comes from the Review Graph (§9) and is only non-zero
when `--with-reviews` ran *and* the author's email resolves to a
GitHub login. Coverage is the per-file normalisation of raw scores:

```
coverage[file, author] = raw_score[file, author] / Σ raw_score[file, *]
```

So coverage sums to 1.0 across all contributors of a file (0.0 if the
file has no raw score at all).

**Parameters** (`OwnershipWeights`, all overridable via a scoring config):

| Name | Default | Meaning |
|---|---|---|
| `commit` | 0.30 | Weight of recency-decayed commit count |
| `volume` | 0.20 | Weight of log-scaled, recency-decayed line volume |
| `recency` | 0.35 | Weight of how recently the author last touched the file (dominant term) |
| `review` | 0.15 | Weight of review activity on the file |
| `decay_lambda` | 0.01 | Exponential decay rate per day (a commit ~69 days old carries half weight) |

**Output:** `FileOwnership` (one per file-author pair) and `OwnershipMap`
(the queryable collection + email→name map). `engine.py:90-115`.

---

## 2. Bus factor

**Measures:** how many people you would need to lose before knowledge of
a file or service is critically thin. Bus factor 1 = single point of
failure.

**Source:** `src/blindspot/risk_models/bus_factor.py`.

**Formula.** Rank contributors by coverage descending, accumulate until
the cumulative coverage reaches `threshold`:

```
bus_factor = min count of top contributors whose Σ coverage ≥ threshold (0.80)
```

It is clamped to a minimum of 1. Risk level maps the integer:

| bus_factor | risk_level |
|---|---|
| ≤ 1 | `critical` |
| 2 | `high` |
| 3 | `medium` |
| ≥ 4 | `healthy` |

**Service rollup.** A "service" is the top-level directory of a path
under the effective service prefix. The prefix is resolved in `cli.py`:
when a source root is detected (`auto_detect_code_root()` — `src/`,
`lib/`, `app/`), and it contains exactly one package-style directory
(e.g. `src/blindspot/`), the prefix becomes `src/blindspot/` and a path
like `src/blindspot/risk_models/correction_load.py` rolls up to service
`risk_models`. With multiple packages under the source root, the prefix
stays at the source root. With no source root, the path's literal first
segment is used. The user can override the source root with
`--code-root`.

Per service, each author's coverages across all files in the service
are summed and divided by the service file count, then the same
cumulative-coverage algorithm runs on those per-person averages.

`top_level_dir()` (`bus_factor.py:27-39`) is what produces the segment
after the prefix is stripped. It has three special buckets:
- `(root)` — files with no parent directory (or directly under the
  service prefix)
- `(config)` — top-level dotfile tooling dirs (`.husky`, `.vscode`,
  `.idea`, `.cursor`, `.devcontainer`, … — see `CONFIG_DOTFILE_PREFIXES`)
  so a one-file `.codex/` does not light up as a critical service
- `(other)` — paths that look malformed (contain `=` or whitespace in
  the first segment, a known leak from rename/diff output)

**Parameters:**

| Name | Default | Meaning |
|---|---|---|
| `threshold` | 0.80 | Cumulative coverage that "counts as knowing" the file/service |

**Output:** `FileBusFactor`, `ServiceBusFactor` — each with `bus_factor`,
`risk_level`, and `top_owners` (ranked `(email, coverage)` tuples).

---

## 3. Knowledge decay

**Measures:** how stale the knowledge of a file is becoming — its primary
owner has stopped touching it *and* others keep changing it. Projects
that staleness 30/60/90 days forward.

**Source:** `src/blindspot/risk_models/knowledge_decay.py`,
weights in `src/blindspot/config.py:DecayWeights`.

**Formulas.** For each file, take its current top owner. `lines_after`
is the total `additions + deletions` made by *other people* after the
owner's last touch. `days_since` is days since the owner's last touch.

```
volatility      = 1 - exp(-volatility_k × lines_after)
person_absence  = 1 - exp(-absence_lambda × days_since)
decay_score     = volatility × volatility_weight + person_absence × absence_weight
```

Both components are in `[0, 1)`, so `decay_score` is too. Projections
re-evaluate `person_absence` at `days_since + offset` for each offset
(volatility is held constant — you cannot predict future churn):

```
projection[offset] = volatility × volatility_weight
                   + (1 - exp(-absence_lambda × (days_since + offset))) × absence_weight
```

Risk level thresholds (`decay_risk_level()`, `knowledge_decay.py:11-18`):

| decay_score | risk_level |
|---|---|
| > 0.75 | `critical` |
| > 0.50 | `high` |
| > 0.25 | `medium` |
| ≤ 0.25 | `low` |

**Service rollup:** per top-level dir — `avg_decay_score`,
`max_decay_score`, count of `critical` files; service risk level is
derived from the *average*.

**Parameters** (`KnowledgeDecayEngine` defaults; `DecayWeights` mirrors them):

| Name | Default | Meaning |
|---|---|---|
| `volatility_weight` | 0.55 | How much "others changed it" matters |
| `absence_weight` | 0.45 | How much "owner went away" matters |
| `absence_lambda` | 0.015 | Per-day decay rate for absence (~46 days → 0.5) |
| `volatility_k` | 0.007 | Per-line decay rate for volatility (~99 lines → 0.5) |
| `projection_days` | (30, 60, 90) | Forecast horizons |

**Output:** `FileDecay` (with `projections` dict), `ServiceDecay`.

---

## 4. Departure simulation

**Measures:** what concretely happens if one or more named people leave —
how much coverage each file loses, which files become *orphans* (no
strong remaining owner), and which services take the biggest hit.

**Source:** `src/blindspot/risk_models/departure.py`.

**Formulas.** For each file, given a set of departing emails:

```
coverage_loss        = Σ coverage of departing contributors on that file
remaining_top_coverage = max coverage among non-departing contributors (0 if none)
becomes_orphan       = remaining_top_coverage < orphan_threshold (0.30)
```

Per-file severity (`departure_severity()`, `departure.py:8-15`):

| condition | severity |
|---|---|
| `becomes_orphan` | `critical` |
| `coverage_loss > 0.70` | `high` |
| `coverage_loss > 0.40` | `medium` |
| otherwise | `low` |

**Service rollup:** per top-level dir — `affected_files` (count where
`coverage_loss > impact_threshold`), `orphaned_files`,
`avg_coverage_loss`, `max_coverage_loss`. Service severity is `critical`
if any file orphaned, else derived from the max single-file loss.

**Parameters** (`DepartureSimulation` defaults):

| Name | Default | Meaning |
|---|---|---|
| `orphan_threshold` | 0.30 | Below this remaining coverage, a file is an orphan |
| `impact_threshold` | 0.40 | Coverage loss above this marks a file "affected" |

**Output:** `FileDepartureImpact`, `ServiceDepartureImpact`,
`DepartureReport` (the top-level result with totals).

Used by the `simulate` command directly, and by `scan` for the top-N
"what if this person leaves" report sections (see `cli.py`,
`--simulate-top-departures`).

---

## 5. Dependency graph build

**Measures:** which files import which other files in the repo — the raw
material for structural-importance ranking (§7) and the module map (§8).

**Source:** `src/blindspot/dependency_graph/builder.py`.

**How it works:**
1. **Pick the code root.** `auto_detect_code_root()` checks `src/`,
   `lib/`, `app/` in order; the first that exists and is non-empty wins,
   otherwise the repo root. The CLI `--code-root` flag overrides this.
   This keeps the graph focused on real code, not the whole repo.
2. **Walk the tree** under that root. Skip: files the `FileFilter` marks
   as binary/generated/ignored; files over `max_file_bytes` (1 MB); and —
   unless `include_tests=True` — anything under `tests/`, `examples/`,
   `docs/`, `benchmarks/` (and variants). Those dirs still count for
   ownership and decay; they are only excluded from the *structural*
   graph because they distort the architectural picture.
3. **First pass (namespace priming).** Languages that need a
   namespace→file index (C#, Java, Kotlin) populate it here.
4. **Second pass (extract).** Each file's language extractor (§6) returns
   the repo-relative paths it depends on; edges are added to a
   `networkx.DiGraph`. If `--llm-graph` is on, the LLM extractor also
   runs per file and its result is unioned in.
5. AST-discovered model annotations are promoted from the extraction
   context onto `graph.model_files`.

**Parameters:**

| Name | Default | Meaning |
|---|---|---|
| `code_root` | `""` (auto) | Repo-relative subtree the graph is built from |
| `include_tests` | `False` | Whether test/example/docs files become graph nodes |
| `max_file_bytes` | 1 048 576 | Files larger than this are skipped |

**Output:** `DependencyGraph` (a `networkx.DiGraph` of file→file edges
with `weight`, plus a `model_files` map).

---

## 6. Language extractors

**Measures:** the in-repo dependencies declared by a single source file.

**Source:** `src/blindspot/dependency_graph/extractors/`.

Eleven languages are supported. **Python is AST-based**; the other ten
(JavaScript/TypeScript, C#/F#/VB, Java, Kotlin, Go, Rust, C/C++, Ruby,
PHP, Swift) are regex-based. All implement the same `ImportExtractor`
protocol: `extensions`, `needs_namespace_index`, `prime_namespace_index()`,
`extract()`.

**Python AST extractor** (`extractors/python.py`) does three things:
1. **Imports.** Walks `ast.Import` / `ast.ImportFrom` nodes; resolves
   each module to a repo file by trying source roots `""`, `src/`,
   `lib/`, `python/` and both `module.py` and `module/__init__.py`.
   Relative imports (`from . import x`) are anchored at the caller's
   package.
2. **Class-inheritance edges.** `class Sub(Base)` adds an edge from this
   file to wherever `Base` was imported from — inheritance is a stronger
   structural bind than a plain import.
3. **Model detection.** A class is flagged as a "model" if it is
   decorated with `@dataclass`, `@define`/`@frozen`/`@mutable`/`@attrs`
   (attrs), `@attr.s`, or `@model`; or if it subclasses `BaseModel`
   (pydantic), `Struct` (msgspec), `Schema`, `TypedDict`, or
   `NamedTuple`. The count per file feeds the "Central models" report
   section.

If `ast.parse` raises `SyntaxError`, the extractor falls back to a regex
that catches `import X` / `from X import Y` (no inheritance or model
detection in fallback mode).

The regex extractors for other languages resolve module paths
heuristically — `go.mod`/`Cargo.toml` module prefixes, Maven/Gradle
layout for the JVM languages, relative path resolution for JS/TS, etc.
They are intentionally simple: a missed edge is better than a wrong one.

**Output:** a `list[str]` of repo-relative paths per file; for Python,
also entries in `ExtractionContext.model_files`.

---

## 7. PageRank importance

**Measures:** structural importance — files that many other files
(transitively) depend on. Weak ownership or high decay on a
high-importance file matters more than on a leaf file.

**Source:** `src/blindspot/dependency_graph/importance.py`.

**How it works:** a pure-Python PageRank (no numpy/scipy). Each edge
`importer → imported` is a vote from the importer for the imported file.
A file's score is the damped sum of incoming votes, each weighted by the
voter's score divided by its out-degree, plus a uniform teleport term.
Dangling nodes (no outgoing edges) have their mass redistributed
uniformly each iteration so total probability stays conserved. Iterates
until the L1 change between rounds drops below `tol` or `max_iter` is hit.

```
teleport          = (1 - damping) / n
score[j]  ← teleport + damping × dangling_mass / n
          + damping × Σ over importers i of j:  score[i] × weight(i,j) / out_weight[i]
```

**Parameters** (`ImportanceEngine` defaults):

| Name | Default | Meaning |
|---|---|---|
| `damping` | 0.85 | Probability of following an edge vs teleporting |
| `max_iter` | 100 | Hard iteration cap |
| `tol` | 1e-6 | L1 convergence tolerance |

**Output:** a `dict[file → importance]` (sums to ~1.0 across all nodes).
`top_n()` turns it into ranked `CentralFile` objects carrying
`importance` + `in_degree`. The `--importance-threshold` CLI flag
(default 0.005) later filters low-importance files out of
recommendations and display tables.

---

## 8. Module aggregation

**Measures:** the repo's architecture at the module level — a readable
Mermaid diagram instead of a thousand-node file graph.

**Source:** `src/blindspot/dependency_graph/aggregation.py`.

**How it works:**
1. **Peel the common prefix.** `_longest_common_parent()` finds the
   directory prefix shared by *every* file (e.g. `src/flask/`). Peeling
   it means the diagram shows internal structure (`json/`, `cli.py`,
   `sansio/`) instead of one giant "everything" module.
2. **Bucket each file** into a module: drop the filename, keep the first
   `depth` (default 2) directory segments of the peeled path. Files with
   no parent dir bucket under `(root)`.
3. **Sum edge weights** between modules; drop intra-module edges (they
   tell you nothing at this zoom level).
4. **Keep the top-K** modules by total degree (in + out), drop edges
   below `min_weight`, emit only modules that participate in a kept edge.

**Central models.** `DependencyGraph.top_models()` ranks the
model-bearing files (from §6) by in-degree, then by model-class count —
these are the structural types the rest of the code is bound to.

**Parameters** (module-level constants):

| Name | Default | Meaning |
|---|---|---|
| `DEFAULT_DEPTH` | 2 | Directory segments kept per module name |
| `DEFAULT_TOP_K` | 12 | Max modules shown in the diagram |
| `DEFAULT_MIN_WEIGHT` | 1 | Minimum aggregated edge weight to draw |

**Output:** `ModuleGraph` (`ModuleNode`s + `ModuleEdge`s); `CentralModel`
list from `top_models()`.

---

## 9. Review graph

**Measures:** review hygiene per file — is review real or a rubber stamp,
is the review load spread across people, how fast do approvals land.

**Source:** `src/blindspot/review_graph/engine.py`. Requires PR data
(`--with-reviews`).

**Formulas.** A reviewer's score on a file:

```
score(reviewer, file) = review_count × 0.5 + comment_count × 1.0
```

(A comment is worth more than a bare review — it is evidence of actual
engagement.)

Per file:
- **rubber_stamp_ratio** — of all `APPROVED` reviews on the file, the
  share where the approver left *no* comment on it:
  `approvals_without_comment / total_approvals`. Higher = more
  stamp-without-reading.
- **diversity_hhi** — `1 - Σ share²` where `share` is each reviewer's
  fraction of the file's reviews (a Herfindahl index, inverted). `1.0` =
  load perfectly spread; `0.0` = one reviewer carries everything.
- **median_approval_latency_seconds** — median, across PRs touching the
  file, of `(first APPROVED review time − PR created time)`. Very low
  values suggest reviews too fast to be substantive.

**Parameters** (module constants): `REVIEW_WEIGHT = 0.5`,
`COMMENT_WEIGHT = 1.0`.

**Output:** `ReviewGraph` — a `(reviewer, file) → score` map plus a
`file → FileReviewStats` map.

---

## 10. Correction Load

**Measures:** the per-author and per-file ratio of recent commits that
are follow-up fixes or reverts. A high ratio is *observable* evidence of
stability debt — work shipped fast but corrections are paying for it. We
look at the work surface, not the person's style.

**Source:** `src/blindspot/risk_models/correction_load.py`, plus
`src/blindspot/diff_analysis/commit_intent.py` for the multilingual
message classifier.

**How it works.**

1. For every non-merge commit, classify intent into one of four categories
   using `classify_commit(message)`:
   - **FEATURE** — `feat:` conventional prefix or feature keywords
   - **FIX** — `fix:` / `bugfix:` / `hotfix:` conventional prefix, or
     fix/bug/typo/regression keywords (EN + TR)
   - **REVERT** — `revert:` prefix, `Revert "..."` git auto-subject, or
     revert/rollback keywords
   - **OTHER** — `chore:`, `docs:`, `refactor:`, anything else
2. Aggregate counts per author and per file.
3. Compute `correction_ratio = (fix + revert) / total`.
4. Filter out authors/files with fewer than `min_commits_for_signal` (5)
   commits — the ratio is noisy below that.
5. Map ratio to a risk level using thresholds.

**Parameters** (`CorrectionLoadEngine` defaults):

| Name | Default | Meaning |
|---|---|---|
| `min_commits_for_signal` | 5 | Authors / files below this are excluded |
| `high_threshold` | 0.35 | Ratio at/above → `high` |
| `critical_threshold` | 0.50 | Ratio at/above → `critical` |

**Output:** `CorrectionLoadReport` with two sorted tuples,
`authors: AuthorCorrectionLoad[]` and `files: FileCorrectionLoad[]`.

**Recommendation tie-in:** Any file whose ratio is `≥ high_threshold`
emits a `Fragile velocity` fragility pattern in §14.

---

## 11. AI Readiness

**Measures:** per-service coverage of AI-native operational artifacts —
agent rules, specs, prompts, architecture decisions, skills. The premise:
in AI-accelerated teams, organizational memory no longer lives only in
code. A service with no artifacts is weaker than its line count suggests
because new contributors (human or AI) have nothing to load.

**This is not an AI-generated-code detector.** It does not look at
content style, statistical fingerprints, or commit shape — only at
whether documented operational context exists.

**Source:** `src/blindspot/risk_models/ai_readiness.py`.

**Categories** (each a Boolean):

| Category | Detected by paths matching |
|---|---|
| `agent_rules` | `CLAUDE.md`, `AGENTS.md`, `.cursor/`, `.github/copilot-instructions.md`, `.aider`, `.windsurf`, `.codex`, `.cody` |
| `specs` | `specs/`, `spec/`, `specifications/` |
| `prompts` | `prompts/`, `prompt/` |
| `architecture` | `ADRs/`, `adr/`, `architecture/`, `docs/architecture/`, `docs/decisions/`, `docs/adr/`, `ARCHITECTURE.md` |
| `skills` | `skills/`, `agents/` |

**How it works.** A single pass over the tracked file list:

1. Match against full paths → repo-level coverage row (`target: "(repo)"`).
2. Group files by `top_level_dir()` (skipping `(config)` / `(root)` /
   `(other)`), strip the prefix, match the rest → one coverage row per
   service.

**Output:** `AIReadinessReport` with one repo-level `AIReadinessCoverage`
and a tuple of service-level coverages. Each exposes
`coverage_count` (0..5) and `coverage_ratio` (0..1).

**Recommendation rule (0.0.5a+).** Services with `coverage_count < 2`
emit a `KNOWLEDGE_TRANSFER` recommendation titled
*"Add AI-readable operational context for {service}"*. Priority is
**MEDIUM** when the service's bus factor is ≤ 1 (the gap compounds with
knowledge concentration), otherwise **LOW**. The description lists the
missing categories so the action is concrete; the evidence string
captures `coverage=N/5, bus_factor=M`. The rule and threshold live on
`RecommendationEngine` as `ai_readiness_min_coverage` (default 2) — see
[recommendation engine](#13-recommendation-engine) §13.

---

## 12. Resilience score

**Measures:** one 0–100 number a non-technical stakeholder can track over
time, synthesised from three independent health signals.

**Source:** `src/blindspot/resilience/score.py`.

**Sub-scores** (each 0–100, higher = healthier):

- **ownership** — `(healthy_ratio − critical_penalty) × 100`, where
  `healthy_ratio` is the share of services with bus factor ≥ 2 and
  `critical_penalty = min(0.30, critical_service_count × 0.05)`.
- **decay** — `(1 − avg_decay_score) × 100` over all files.
- **review** — `((1 − avg_rubber_stamp) × 0.6 + avg_diversity × 0.4) × 100`
  over files that have at least one review. `None` if no review data.

**Overall.** A weighted average over *available* sub-scores only —
missing signals are excluded from the denominator, not treated as zero:

```
overall = Σ (weight[k] × sub[k])  /  Σ weight[k]      for k in available
```

**Bands** (`_band()`):

| overall | band |
|---|---|
| ≥ 80 | `Strong` |
| ≥ 60 | `Moderate` |
| ≥ 40 | `Fragile` |
| < 40 | `Critical` |

**Parameters** (`DEFAULT_WEIGHTS`):

| Sub-score | Weight |
|---|---|
| ownership | 0.40 |
| decay | 0.35 |
| review | 0.25 |

**Output:** `ResilienceScore` — `overall`, the three sub-scores (each
`int | None`), the `band`, and a one-line `summary` naming the weakest
dimension.

**Letter grades (0.0.5a+).** Each score also exposes a letter grade via
the `letter_grade(value)` helper and the `overall_grade`,
`ownership_grade`, `decay_grade`, `review_grade` properties:

| Score | Grade |
|---|---|
| ≥ 90 | `A` |
| ≥ 80 | `B` |
| ≥ 70 | `C` |
| ≥ 60 | `D` |
| < 60 | `F` |

The HTML report shows the letter grade beside each numeric sub-score
and beside the overall score. The rule-based narrator's
"weakest dimension" sentence also includes the grade in parentheses
(e.g. *"Weakest dimension: ownership concentration (F)."*).

---

## 13. Recommendation engine

**Measures:** turns all the signals above into a prioritised, deduplicated
list of concrete next steps — and tags recurring ones with a named
fragility pattern.

**Source:** `src/blindspot/actions/recommender.py`,
`src/blindspot/actions/models.py`.

**Seven rules.** Each emits at most `max_per_rule` (5) actions:

| Rule | Fires when | Priority | Fragility pattern |
|---|---|---|---|
| Service bus factor | service `bus_factor == 1` | HIGH if ≥5 files else MEDIUM | `single-owner-concentration` |
| File decay | `decay_score ≥ 0.50` and passes importance filter | HIGH if ≥0.75 else MEDIUM | — |
| Rubber stamp | `rubber_stamp_ratio ≥ 0.70`, ≥2 reviews, file is code | MEDIUM | `review-without-scrutiny` |
| Reviewer diversity | `diversity_hhi < 0.20`, ≥3 reviews, file is code | LOW | — |
| Fast approval | median approval latency < 1800 s, ≥3 samples, file is code | MEDIUM | `review-without-scrutiny` |
| Correction load | file `correction_ratio ≥ 0.35`, file is code | MEDIUM (HIGH if `critical`) | `fragile-velocity` |
| AI-readiness gap | service `coverage_count < 2` | MEDIUM if bus factor ≤ 1 else LOW | — |
| CODEOWNERS | declared owner mismatched or stale | MEDIUM (mismatch) / LOW (stale) | — |

**Importance filter.** When an importance map is present (dependency
graph ran), file-targeted rules drop any file whose PageRank importance
is below `importance_threshold` (0.005) — this is what stops one-shot
bootstrap scripts and leaf utilities from generating noise.

**Fragility patterns** (`FragilityPattern` enum) — the named AI-era
failure modes the report surfaces as badges:
- **`review-without-scrutiny`** — approvals land without substantive
  review (rubber stamp + fast approval).
- **`single-owner-concentration`** — a whole service rests on one person.
- **`fragile-velocity`** — a file ships fast but follow-up fixes/reverts
  pay the bill (high correction load).

**Parameters** (`RecommendationEngine` defaults):

| Name | Default | Meaning |
|---|---|---|
| `decay_critical_threshold` | 0.75 | Decay at/above → HIGH priority |
| `decay_high_threshold` | 0.50 | Minimum decay to recommend at all |
| `rubber_stamp_threshold` | 0.70 | Rubber-stamp ratio that triggers the rule |
| `diversity_floor` | 0.20 | HHI diversity below this triggers the rule |
| `fast_approval_seconds` | 1800 | Median latency below this triggers the rule |
| `min_reviews_for_rubber_stamp` | 2 | Minimum reviews before rubber-stamp applies |
| `min_reviews_for_diversity` | 3 | Minimum reviews before diversity applies |
| `min_approvals_for_latency` | 3 | Minimum approval samples before latency applies |
| `max_per_rule` | 5 | Cap on actions emitted per rule |
| `importance_threshold` | 0.005 | PageRank floor for file-targeted rules |

**Output:** `RecommendedAction` list — each with priority, category,
title, description, target, evidence string, and optional `pattern`.

---

## 15. Diff classifier

**Measures:** what each file and PR actually *is* — code, test, docs, or
chore — so the report can separate real feature work from noise.

**Source:** `src/blindspot/diff_analysis/classifier.py`. Requires PR data
for the PR-level parts.

**`classify_file(path)` → `code | test | docs | chore`:**
- **test** — path contains a test directory (`test`, `tests`,
  `__tests__`, `spec`, `e2e`, `benchmarks`, …) *or* the basename matches
  a language test convention (`test_*.py`, `*_test.go`, `*.test.ts`,
  `*_spec.rb`, `FooTest.java`, `FooSpec.cs`, …).
- **docs** — path contains a docs directory, or basename ends `.md` /
  `.rst` / `.adoc` (excluding `LICENSE`).
- **chore** — under `.github/` / `.gitlab/` / `.circleci/`; or a known
  chore basename (`Dockerfile`, `Makefile`, `.gitignore`,
  `.pre-commit-config.yaml`, `renovate.json`, …); or a top-level
  `.toml` / `.cfg` / `.ini`.
- **code** — everything else.

**`classify_pr(pr)` → `PRCategory`:**

| Condition | Category |
|---|---|
| no files | `chore` |
| has code files, churn = 0 | `refactor` |
| has code files, `additions/churn > 0.7` | `feature` |
| has code files, `additions/churn < 0.3` | `cleanup` |
| has code files, in between | `refactor` |
| no code, mostly test files | `test` |
| no code, mostly docs files | `docs` |
| otherwise | `chore` |

`summarise()` aggregates: per-category counts and ratios across all PRs,
plus the top 15 churned files (ranked by total `additions + deletions`).

**Output:** `PRClassification` per PR, `FileChurn` per file,
`DiffChurnSummary` overall.

---

## 16. Trend engine

**Measures:** whether resilience is improving or degrading — resilience
score recomputed at several points in the past.

**Source:** `src/blindspot/trend/engine.py`. Requires `--with-trend`.

**How it works.** For each offset in `offsets_days` (default
`90, 60, 30, 0`, processed oldest-first): slice commits to those
authored on/before `now − offset`, then re-run ownership → bus factor →
decay → resilience at that `as_of`. Only ownership and decay sub-scores
are computed historically — review and activity sub-scores need
present-only data (live review graph, AI baselines), so they are
omitted from past snapshots.

`delta_overall` is the change in overall score from the oldest snapshot
to the latest.

**Parameters:**

| Name | Default | Meaning |
|---|---|---|
| `offsets_days` | (90, 60, 30, 0) | Days-ago points to snapshot |

**Output:** `ResilienceTrend` — a tuple of `TrendSnapshot`
(`as_of`, `days_ago`, `ResilienceScore`).

---

## 17. CODEOWNERS validation

**Measures:** whether a repo's declared `CODEOWNERS` file matches who
actually owns the code.

**Source:** `src/blindspot/codeowners/parser.py` (parsing),
`src/blindspot/codeowners/engine.py` (validation). Requires
`--check-codeowners` (on by default) and a `CODEOWNERS` file in the repo.

**How it works.** The parser reads CODEOWNERS with last-rule-wins
semantics (later patterns override earlier ones). For each file with
ownership data, the validator assigns one category:

| Category | Meaning |
|---|---|
| `aligned` | Declared owner *is* the actual top owner, touched recently |
| `mismatch` | Declared individuals don't include the actual top owner (and actual coverage ≥ 0.4), or the declared owner is present but not top |
| `stale` | Declared owner matches but hasn't touched the file in > `stale_days` |
| `team_only` | Rule names only `@org/team` owners — cannot validate against commit data |
| `orphan` | No CODEOWNERS rule matches the file at all |

Declared `@username` entries are matched against actual commit emails
(handles `username@…` and `…+username@users.noreply.github.com` forms).

**Parameters** (`CodeOwnersValidator` / module constants):

| Name | Default | Meaning |
|---|---|---|
| `stale_days` | 90 | Days since declared owner's last touch before "stale" |
| `MIN_COVERAGE_FOR_MISMATCH` | 0.4 | Actual top-owner coverage needed to flag a mismatch |

**Output:** `CodeOwnersReport` — all `CodeOwnersFinding`s, with
convenience properties (`orphans`, `mismatches`, `stale`, `team_only`,
`aligned`, `coverage_ratio`).

---

## See also

- [architecture.md](architecture.md) — how these engines are wired into
  the `scan` / `simulate` pipelines.
- [outputs.md](outputs.md) — where each algorithm's result shows up in
  the HTML report.
- [glossary.md](glossary.md) — one-line definitions of every term used
  above.
