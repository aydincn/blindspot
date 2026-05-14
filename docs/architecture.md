# Architecture

How Blindspot is wired: the modules, the direction data flows between
them, and the exact order of the two analysis pipelines.

---

## The shape of the system

Blindspot is a single-process CLI. There is no server, no database, no
daemon. A run reads a local git repository (and optionally a hosting
provider's API), holds everything in memory, and writes one
self-contained HTML file.

```
                         ┌──────────────┐
                         │   cli.py     │  orchestrator: parses flags,
                         │ (scan /      │  calls every engine in order,
                         │  simulate)   │  assembles the report context
                         └──────┬───────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   ┌────▼─────┐          ┌───────▼────────┐       ┌──────▼──────┐
   │ collector│  input   │  analysis      │       │   report    │  output
   │  layer   │ ───────► │  engines       │ ────► │   layer     │
   └──────────┘          └────────────────┘       └─────────────┘
   git history,          ownership, risk_models,   ReportContext →
   GitHub/Bitbucket      dependency_graph,         Jinja2 template →
   PR data,              review_graph, ai_signal,  single HTML file
   CODEOWNERS,           diff_analysis, resilience,
   mailmap, filters      codeowners, trend, actions,
                         narrative
```

Dependencies only point inward-to-output: `collector` knows nothing
about `report`; `report` consumes a single `ReportContext` dataclass and
nothing else. `cli.py` is the only place that knows about all of them.

---

## Modules

Each directory under `src/blindspot/` is one module with one job.

| Module | Responsibility |
|---|---|
| `cli.py` | Orchestrator. Defines the `scan`, `simulate`, `version` commands; calls every engine in order; builds the report context. |
| `config.py` | Pydantic models for the scoring config (ownership + decay weights). Loaded from an optional YAML; defaults baked in. |
| `collector/` | Reads raw input: git commits (`git.py`), `.mailmap` identity merging (`mailmap.py`), bot detection (`bots.py`), binary/generated file filtering (`filters.py`), and the GitHub + Bitbucket PR-data providers. |
| `collector/review_models.py` | The provider-agnostic `PullRequest` / `Review` / `ReviewComment` / `PullRequestFile` dataclasses — produced identically by the GitHub and Bitbucket collectors. |
| `ownership/` | Computes weighted per-file ownership coverage from commits (+ optional review signal). Produces `OwnershipMap`. |
| `risk_models/` | Bus factor (`bus_factor.py`), knowledge decay (`knowledge_decay.py`), departure simulation (`departure.py`) — the three core risk algorithms. |
| `dependency_graph/` | Builds the file import graph (`builder.py` + 11 language `extractors/`), ranks files by PageRank (`importance.py`), rolls up to a module map (`aggregation.py`), and an optional LLM import resolver (`llm_fallback.py`). |
| `review_graph/` | Turns PR review data into per-file review-hygiene stats (rubber-stamp ratio, reviewer diversity, approval latency). |
| `ai_signal/` | Experimental author profiling: AI-amplification detector, code-quality signal, and the classifier that combines them. |
| `diff_analysis/` | Classifies files (code/test/docs/chore) and PRs (feature/refactor/cleanup/test/docs/chore); produces the churn summary. |
| `codeowners/` | Parses a `CODEOWNERS` file and validates it against actual ownership (aligned/mismatch/stale/orphan/team_only). |
| `resilience/` | Composite 0–100 Engineering Resilience Score from the ownership / decay / review / activity sub-signals. |
| `trend/` | Recomputes resilience at past points in time (90/60/30/0 days ago) for the trend view. |
| `actions/` | The recommendation engine — seven rules that turn signals into a prioritised action list, with fragility-pattern tagging. |
| `narrative/` | Optional LLM layer: an executive summary on top of the report, and a departure briefing. Provider/model/key config lives here. |
| `report/` | The output layer: `ReportContext` / `DepartureContext` dataclasses, the Jinja2 renderer, and the two HTML templates. |

For the algorithm inside each engine, see
[algorithms.md](algorithms.md).

---

## The `scan` pipeline

`blindspot scan <repo>` runs the engines in this exact order
(`cli.py`, line references in parentheses):

1. **Collect commits** — `GitCollector.collect()` reads the git log for
   the `--since-days` window, applies the file filter and `.mailmap`,
   yields `Commit` objects. *(cli.py:217)*
2. **Collect review data** *(if `--with-reviews`)* — auto-detect the
   remote (GitHub first, then Bitbucket Cloud), fetch PRs, build the
   `ReviewGraph` and the diff churn summary. *(cli.py:324)*
3. **Ownership** — `OwnershipEngine.compute(commits, review_graph)`
   produces the `OwnershipMap`. The review graph feeds the review term
   of the ownership score, which is why it runs *before* this step.
   *(cli.py:334)*
4. **CODEOWNERS validation** *(if `--check-codeowners`, on by default)* —
   `CodeOwnersValidator.validate()` against the ownership map.
   *(cli.py:342)*
5. **Bus factor + decay** — `BusFactorEngine` (files + services) and
   `KnowledgeDecayEngine` (files + services). *(cli.py:352-353)*
6. **Dependency graph** *(unless `--no-dependency-graph`)* —
   `DependencyGraphBuilder.build()` → `ImportanceEngine.compute()` (the
   importance map) → `aggregate_modules()` (the module map) →
   `top_models()` (central models). *(cli.py:397-404)*
7. **AI signal** *(if `--experimental-ai-signal`)* —
   `AIAmplificationDetector` → `QualitySignalEngine` → `AuthorProfiler`.
   *(cli.py:566-570)*
8. **Resilience score** — `ResilienceScoreEngine.compute()` over the
   bus-factor / decay / review / author-profile signals. *(cli.py:614)*
9. **Trend** *(if `--with-trend`)* — `TrendEngine.compute()` replays
   ownership + decay + resilience at 90/60/30/0 days ago. *(cli.py:685)*
10. **Departure scenarios** *(if `--simulate-top-departures` > 0)* —
    `DepartureSimulation.simulate()` for the top-N contributors by
    aggregate coverage. *(cli.py:724)*
11. **Assemble `ReportContext`** — every signal above is packed into the
    single context dataclass. *(cli.py:732)*
12. **Recommendations** — `RecommendationEngine.recommend()` over a
    `RecommendationContext` built from the same signals. *(cli.py:776)*
13. **Narrative** *(if `--with-narrative`)* — `NarrativeEngine.summarize()`
    asks the LLM for an executive summary + headline + rationales.
    *(cli.py:814)*
14. **Render** — `ReportRenderer.render(ctx)` → the HTML file at
    `--output`. *(cli.py:832)*

Steps 2, 4, 6, 7, 9, 10, 13 are conditional on flags; the rest always
run.

---

## The `simulate` pipeline

`blindspot simulate -p <email> <repo>` is the focused "what if this
person leaves" report:

1. **Collect commits** — `GitCollector.collect()`. *(cli.py:860)*
2. **Ownership** — `OwnershipEngine.compute(commits)` (no review graph
   in this path). *(cli.py:861)*
3. **Departure simulation** — `DepartureSimulation.simulate(ownership,
   person)` for the named people. *(cli.py:862)*
4. **Remaining-owner gaps** — `compute_remaining_gaps()` ranks who would
   inherit the orphaned files.
5. **Narrative** *(if `--with-narrative`)* —
   `NarrativeEngine.summarize_departure()`. *(cli.py:930)*
6. **Render** — `ReportRenderer.render_departure(ctx)` → the HTML file.
   *(cli.py:965)*

---

## Key shared types

These dataclasses are the seams between modules — most cross-module data
flows through one of them:

| Type | Defined in | Carries |
|---|---|---|
| `Commit` / `FileChange` | `collector/models.py` | One git commit: sha, author, timestamp, message, file changes |
| `OwnershipMap` | `ownership/models.py` | All `FileOwnership` scores + an email→name map; the input to bus factor, decay, departure, CODEOWNERS |
| `PullRequest` | `collector/review_models.py` | Provider-agnostic PR: reviews, comments, files — same shape from GitHub and Bitbucket |
| `DependencyGraph` | `dependency_graph/models.py` | The `networkx` file graph + the `model_files` map |
| `ReportContext` | `report/context.py` | Everything the `scan` HTML template needs — assembled once, rendered once |
| `DepartureContext` | `report/context.py` | Everything the `simulate` HTML template needs |
| `ResilienceScore` | `resilience/score.py` | The composite score + four sub-scores + band + summary |

---

## Design constraints baked into the structure

- **One process, one file out.** No server or DB means the whole thing
  is `pip install` + run. The report is a single HTML file you can email.
- **`collector` is the only thing that touches the network**, and only
  when `--with-reviews` or `--with-narrative` / `--llm-graph` is set. A
  plain `scan` is fully offline.
- **`report` depends only on `ReportContext`.** The template never calls
  an engine — all computation is done before rendering. This is what
  makes the output deterministic and the template easy to change.
- **Credentials never come from environment variables.** The three
  config loaders (`narrative/config.py`, `collector/github/config.py`,
  `collector/bitbucket/config.py`) read CLI flags and `.blindspot.yaml`
  only. See [configuration.md](configuration.md).

---

## See also

- [algorithms.md](algorithms.md) — what each engine actually computes.
- [cli-reference.md](cli-reference.md) — every flag that toggles a
  pipeline step.
- [outputs.md](outputs.md) — what the assembled `ReportContext` becomes
  on screen.
