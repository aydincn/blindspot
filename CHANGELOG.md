# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.0.3] — 2026-05-15 (Pre-alpha)

The "scan-and-go" release. `pip install blindspot && blindspot scan /repo`
now produces a complete report — narrative included — out of the box,
with zero setup. Heavier features are still available, surfaced via
contextual hints in the report itself.

### New
- **Rule-based narrator** (Tier 0) — produces a deterministic executive
  summary, headline action, and per-recommendation rationales from
  `ReportContext`. No API key, no network, no model. Bilingual (EN + TR).
- **OpenAI client** (Tier 1) — `--provider openai` now works alongside
  Anthropic. stdlib-only HTTP, no new dependency.
- **In-report upgrade hints** — when a feature is unavailable (no cloud
  key → rule-based; no review credentials → no PR metrics) the report
  surfaces a small, contextual notice telling the user *exactly* how to
  enable it. CLI `--help` is no longer where you have to look.

### Changed (breaking, pre-alpha 0.x)
- `--with-trend` removed — trend is **always on** now.
- `--with-narrative` removed — narrative is **always on** (rule-based by
  default; cloud LLM if `narrative.api_key` is configured).
- `--with-reviews` is now auto-mode by default — tries when credentials
  are available (token, gh CLI, or Bitbucket app password), silently
  skips when not. Pass `--no-reviews` to opt out. The report explains
  how to enable when skipped.
- `--simulate-top-departures` default raised `3 → 6`.
- `--llm-graph` + `--llm-graph-max-calls` removed; the static AST +
  10 regex extractors cover supported languages well enough that the LLM
  augmentation wasn't earning its cost.
- `[ai]` optional dependency removed from `pyproject.toml` — was never
  actually used; rule-based narrator and cloud clients are all stdlib.

### Internal
- `narrative.config.load_narrative_config` no longer raises when
  `api_key` is missing — returns an empty config and the caller falls
  back to the rule-based narrator.
- New `generate_narrative(cfg, ctx, language)` entry point chooses
  cloud or rule-based based on `cfg.api_key`.
- `ReportContext.detected_remote` (`"github"` / `"bitbucket"` / `None`)
  drives the review-section hint targeting.

## [0.0.2] — 2026-05-14 (Pre-alpha)

First PyPI release.

### Departure reporting
- Standalone HTML departure report for the `simulate` command (`--output`)
- "Departure scenarios" and "Central models" sections in the scan report
- Named fragility patterns on recommendations: review-without-scrutiny,
  single-owner-concentration, velocity-without-review

### Dependency graph
- Auto-detect code root (`src/` / `lib/` / `app/`); test, example, and
  docs directories are excluded from the structural graph by default
- AST-based Python extractor: import resolution, class-inheritance edges,
  and data-model detection (dataclass, pydantic, attrs, msgspec, …)
- Module aggregation peels the common parent prefix so internal
  architecture is visible

### Review-data providers
- Bitbucket Cloud provider (remote detection, REST v2.0 client,
  app-password auth) — `--with-reviews` now works on Bitbucket repos
- Shared provider-agnostic pull-request models
- `--github-token` flag and `github:` config block for private repos
  without the `gh` CLI

### Documentation
- New `docs/` folder: overview, quickstart, architecture, algorithms,
  CLI reference, configuration, outputs, and glossary

## [0.0.1] — 2026-05-13 (Pre-alpha)

Initial public release.

### Knowledge map
- Ownership engine with recency- and review-weighted contribution scoring
- Bus factor per file and per service (top-level directory)
- Review-graph reviewer-coverage analysis
- File-level dependency graph with PageRank-based structural importance
- Module-level Mermaid diagram in the HTML report

### AI risk signals
- "Fake velocity" detector for AI-amplified commits
- Commit quality heuristics (size, churn, review depth)
- Per-author AI-usage profile

### Departure simulation
- Per-person knowledge-loss projection
- Service-level impact when one or more people leave

### Reporting
- Single self-contained HTML report (Jinja2 template, embedded styles)
- Recommender engine: risk → prioritised, deduplicated action list
- Importance threshold filtering across recommendations and display tables
- Optional LLM-generated executive summary (Anthropic backend, TR/EN)

### Languages supported by the dependency extractor
Python · JavaScript / TypeScript (incl. `.mjs`, `.cjs`, JSX, TSX) ·
C# + F# · Java · Kotlin · Go · Rust · C/C++ · Ruby · PHP · Swift.
Opt-in `--llm-graph` flag augments the static result with an LLM call.

### Other
- CODEOWNERS parser with team-only fallback messaging
- Trend module (time-series view over the configured window)
- GitHub PR + reviewer + diffstat collector (`--with-reviews`)
- Configurable via CLI flags, `.blindspot.yaml` (project), or
  `~/.config/blindspot/config.yaml` (user). API keys are never read from
  environment variables.
