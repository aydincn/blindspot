# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.0.5d0] — 2026-05-16 (Pre-alpha)

The "CTO-level credibility" pass. Three fixes driven by saha testleri
across flask / rich / awesome / kubernetes / fastapi — the kind of
embarrassments a single demo would surface.

### New
- **Wider bot pattern matching** — `*-robot`, `*-bot`, `bot-*`,
  `automation*`, `ci-*` identity patterns are now caught alongside the
  existing `[bot]` suffix and known-name fragments. Closes a regression
  where Kubernetes Release Robot became the headline recommendation in
  a k8s scan ("Pair Kubernetes Release Robot on CHANGELOG — bus factor
  1 across 5 files").
- **Support-service exclusion** — new `SUPPORT_SERVICES` set in
  `actions/recommender.py` (`.github`, `docs`, `tests`, `scripts`,
  `examples`, `hack`, `vendor`, `(root)`, `(config)`, `(other)`, and
  friends). The bus-factor + AI-readiness rules skip these surfaces:
  they appear in the data tables for awareness, but no action is
  emitted. CI workflows being maintained by one engineer is by design,
  not a fragility to fix.
- **Structural-note framing** — when the resilience band reads
  "Fragile" or "Critical" *and* the ownership sub-score is below 40
  (which is structurally typical for founder-led / single-maintainer
  projects), the executive summary now appends a one-line note:
  *"This is a structural property — typical for founder-led or
  single-maintainer projects — not a verdict on project health."*
  EN + TR.

### Why these three together
Three independent failure modes saha testlerinde aynı boardroom
demo'sunu mahvediyordu: (a) bot kişi sanılıyor; (b) ".github" gibi
support directory'ler "diversify ownership of" önerisi alıyor; (c)
"Critical" band'ı mature OSS için panik mesajı veriyor. Hepsi 0.0.5d
ile kapanıyor; recommendation tablosu artık eylem-üretmeyen gürültüden
arınıyor.

## [0.0.5c0] — 2026-05-16 (Pre-alpha)

The "service granularity" hotfix. Recommendations and the service risk
map no longer collapse a Python package into one giant `src` (or `lib`)
pseudo-service.

### New
- **Smart `service_of` factory** — when scanning a repo with a source
  root that contains a single package (e.g. `src/blindspot/`), services
  are now the directories *inside* the package (`risk_models`, `actions`,
  `narrative`, `report`, `collector`, …) instead of the source root
  itself. Auto-detected via `auto_detect_code_root()` + a child-count
  probe; the user can still override with `--code-root`.
- **`Service root:` line** in scan output names the prefix that was
  stripped, so the granularity choice is visible.
- **"Start with: X" enrichment** — service-level diversification
  recommendations now name the highest-importance code file in the
  service (e.g. *"Start with: src/blindspot/dependency_graph/extractors/
  base.py (highest importance in this service)"*). The evidence string
  also gains `top_file=...`. New `RecommendationContext.service_top_files`
  field carries the map; built in `cli.py` from `critical_files` +
  `importance_map`.

### Changed
- Service tables (`Service risk map` in HTML + the terminal "Service
  risk" table) now show package-internal modules instead of `src` /
  `lib`. Decay-by-service and multi-person departure scenarios use the
  same definition for consistency.

### Removed (BREAKING)
- **CODEOWNERS validation HTML section** removed. The validator engine
  still runs and still emits `CODEOWNERS_UPDATE` recommendations for
  mismatched and stale entries — the standalone counts/sub-tables block
  was redundant next to the punch list and added noise. Consumers
  parsing the HTML for `<h2>CODEOWNERS validation</h2>` will break.

### Internal
- All `for_services(...)` and `simulate(...)` call sites in `cli.py`
  now pass `service_of=` explicitly; the engines themselves were
  unchanged (they already accepted the injection).

## [0.0.5b0] — 2026-05-16 (Pre-alpha)

The "strategic showcase" release. Multi-person departure scenarios make
the signals from 0.0.4 + 0.0.5a boardroom-presentable, and the README is
repositioned around the same theme.

The single grouped report layout (one mode, no flag) is the explicit
design choice — the TL;DR group already sits at the top of every report
for executive consumption; detailed groups follow for drill-down.

### New
- **Multi-person departure simulation** — new flag
  `--simulate-departures "alice@x.com,bob@x.com,carol@x.com"` adds a
  combined "if these N people leave together" card to the report on top
  of the per-contributor top-N scenarios. The card spans the full grid
  width and uses pill chips for each person.
- **README hero revamp** — value-first opening (Engineering resilience
  for AI-accelerated teams), explicit multi-person example up front,
  capabilities re-organised as a "what it measures" table.

## [0.0.5a0] — 2026-05-16 (Pre-alpha)

The "report hygiene" release. The HTML report is streamlined — fewer
sections, the strongest signals surfaced first, and AI-readiness now
generates recommendations instead of just displaying coverage.

### New
- **AI-readiness gap recommendation** — services with fewer than 2/5
  AI-native context categories now emit a `KNOWLEDGE_TRANSFER`
  recommendation. Priority is bumped to MEDIUM when the service's bus
  factor is ≤ 1 (the gap compounds with knowledge concentration).
- **Risk inventory surfacing** for both new signals: the executive
  summary's risk-inventory paragraph now lists
  *"N file(s) carry high correction load"* and
  *"N service(s) lack AI-readable operational context"*.
- **Headline picker** integrates correction load — when no higher-priority
  signal fires, a fragile-velocity file becomes the headline.
- **Rule-based narrator rationales** for Fragile-velocity actions and
  AI-readiness-gap actions (EN + TR).
- **Letter grades (A-F)** for Engineering Resilience sub-scores. Overall
  score and each of Ownership / Decay / Review now show a letter grade
  beside the numeric value.
- **4-group section layout** — the report is organised under four headers:
  *TL;DR*, *People & Ownership*, *Knowledge State*, *Process Quality*.
  Module dependency map moved into a collapsible "Architecture details"
  group at the bottom.

### Changed
- **Recommendations moved to the top** (was 13th of 17 sections; now
  immediately under the resilience score).
- **`--simulate-top-departures` default 6 → 3** — six cards crowded the
  view; three is enough for "the most critical contributors". Pass
  `--simulate-top-departures 6` to restore the 0.0.4 behaviour.

### Removed (BREAKING, pre-alpha 0.x)
- HTML report sections removed: **Activity summary** (basic git stats
  every tool provides), **Central models** (niche, low CTO value),
  **Structural backbone** (used only as an internal filter — backend
  computation kept, display dropped), **PR activity mix + top churned
  files** (correction load is the stronger signal). The engines still
  compute the data; only the display was dropped.
- Consumers parsing the HTML by section title will break — pre-alpha
  0.x permits this.

## [0.0.4] — 2026-05-15 (Pre-alpha)

The "user theses" release. Two new observable signals replace the
speculative AI-velocity detection: **Correction Load** (per-file ratio
of follow-up fixes/reverts) and **AI Readiness** (coverage of AI-native
operational artifacts). Both treat work surfaces, not people, as the
unit of analysis.

### New
- **Correction Load** (`risk_models.correction_load`) — classifies each
  commit's intent (FIX / REVERT / FEATURE / OTHER) via a multilingual
  commit-message parser (`diff_analysis.commit_intent`, EN + TR), then
  computes per-author and per-file correction ratios. High ratios mark
  fragile-velocity work surfaces. A new `Fragile velocity` fragility
  pattern is emitted in recommendations.
- **AI Readiness** (`risk_models.ai_readiness`) — per-service coverage
  matrix for AI-native operational artifacts: agent rules (`CLAUDE.md`,
  `.cursor/rules`, copilot instructions), specs, prompts, architecture
  decisions, skills. This is **not** an AI-generated-code detector — it
  measures whether organizational memory exists for new contributors
  (human or AI) to load.

### Changed
- README capabilities section updated to reflect Correction Load and
  AI Readiness; roadmap reordered.

### Removed (BREAKING, pre-alpha 0.x)
- `ai_signal/` module removed in full. The speculative `FAKE_VELOCITY`
  author classification, `AIAmplificationDetector`, `QualitySignalEngine`,
  `AuthorProfiler` and the `--experimental-ai-signal` flag are gone.
  Rationale: surveillance-shaped framing and speculative inference are
  incompatible with the project's evidence-over-inference principle.
  The replacement signals (Correction Load, AI Readiness) look at the
  work surface, not the author. The `ai_signal` name is reserved for
  future use in the AI-native operational context family.
- `FragilityPattern.VELOCITY_WITHOUT_REVIEW` and the related
  `headline_velocity` / `rationale_velocity` rule-based narrator
  labels removed.
- `ResilienceScore.activity` sub-score removed; weights renormalised
  across ownership / decay / review. Authors of code calling the
  engine directly should drop the `author_profiles` argument.

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
