# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.2.0] — 2026-05-17 (Pre-alpha)

The "geri dönüş" release. A head-of-engineering review of the v0.1.0
report landed a blunt verdict: *akademik vibe, çok metrik metrik,
anlamlandırmak zor.* It was right. Across 0.0.4 → 0.1.0 the report
grew to 15+ sections — knowledge graphs, pattern cards, silo
detection, change-fear, timeline events. The product drifted from its
value proposition into a metric pile.

0.2.0 returns to the value proposition: **six concrete questions, each
with a one-number answer a CTO/VP reads in one glance.**

### Changed
- **Standard report is now six "key signals"** — each a single number
  + letter grade + one-line plain-English meaning:
    1. Ownership concentration — services on a single owner
    2. Single-engineer dependency — files orphaned by a top departure
    3. Knowledge decay — files the owner drifted away from
    4. Review depth — files approved without scrutiny
    5. Correction load — files with a heavy bugfix tail
    6. AI readiness — services lacking AI-readable operational context
  No formulas on the surface, no jargon. The executive summary and the
  per-signal explanations stay — that was explicit feedback.
- **Default report 1584 → ~630 lines** on a typical repo. One screen
  of signal, not fifteen sections of detail.

### New
- **`--detailed` flag** — opt-in for the deep-dive sections (knowledge
  graph, change-fear index, hidden silos, pattern detection, resilience
  trend, service risk map, departure cards, module dependency map).
  Off by default. The code for all of these is unchanged and fully
  tested — it just no longer ships in the standard report.

### Fixed
- **AI-readiness false positive** — `.claude/`, `.config/`, `.cache/`
  are now treated as tooling-config directories (joined the existing
  `.cursor` / `.vscode` / `.idea` group). Saha test caught uv's top
  recommendation being "Add AI-readable operational context for
  `.claude`" — ironic, since `.claude` *is* the AI tooling directory.

### Philosophy
This is the last sprint of the simplification arc. The product does
one thing: tell a CTO where the organisational fragility is, in plain
language, in one screen. Everything that doesn't serve that is behind
`--detailed`.

## [0.1.0] — 2026-05-17 (Pre-alpha)

The "5 temel kategori — odak görünürlüğü" release. The resilience
score grew up — three sub-scores became five. A CTO sees which of the
five product axes is dragging at first glance, and the weakest one
carries a "FOCUS" badge so they know where to start.

Marketing yüzeyleri (README hero, tagline, pyproject description)
dokunulmadı — kullanıcı kararı: mevcut framing zaten doğru pozisyonu
söylüyor.

### New
- **5 sub-scores instead of 3** — ownership, decay, review (existing),
  plus **correction load** and **AI readiness**. Each carries its own
  letter grade (A–F) badge.
- **FOCUS highlight** — the weakest sub-score in any given scan gets a
  small "FOCUS" badge plus a subtle outline. CTO's eye lands on the
  problem axis in 5 seconds, no composite-survivability-score
  abstraction needed.
- **`ResilienceScore.focus_dimension()`** — programmatic access to
  whichever sub-score is the worst. Used by the template; available
  to downstream consumers.

### Changed
- **Score weights renormalised** (BREAKING for trend continuity):
    * ownership 0.40 → 0.30
    * decay 0.35 → 0.25
    * review 0.25 → 0.20
    * correction load: new 0.15
    * AI readiness: new 0.10
  Overall score lands within ±5 of the 0.0.9 number on a typical repo,
  but the breakdown is now five-dimensional. Historical trend
  snapshots are re-computed under the new formula.

### Not in this release (deliberate)
- ❌ No composite "Survivability Score" tek rakamı (user feedback:
  "iddialı", kategori-bazlı odak yeterli)
- ❌ No tagline / README hero / pyproject description değişimi
- ❌ No marketing manifesto

### Saha re-test verdict (5 repo, 2026-05-17 post-ship)
Cohort: Blindspot self · `blind_spot` (eski clone, 6 commit) · `openpy`
(OpenAI Python SDK, team) · `kubernetes` (multi-org, 137K commits) ·
`openclaw` (49K commits, çoklu maintainer).

**Çalışan kazanımlar (saha doğrulamalı):**
- Executive brief her repoda overall band + top 3 risks + business
  implication üretiyor. Önceki "1 dakikada ne yapayım?" havada
  kalmıyor.
- 5 sub-score + FOCUS badge gerçek odak üretiyor: Blindspot/blind_spot
  → AI Readiness · openpy → **Correction** (yeni sub-score'un
  doğrudan işe yaraması) · kubernetes/openclaw → AI Readiness (mature
  infra'da operational doküman gap'i).
- Compound risk merging: Blindspot'ta 8+ ayrı satır → 3 compound + 2
  dağınık. Aynı dosya 4 satırda tekrar etmiyor.
- Confidence layer doğru ağırlandırma: kubernetes (137K commits) →
  3 HIGH; openclaw (49K commits) → 10 HIGH; Blindspot self (60 days,
  1 author) → 1 HIGH/6 LOW; blind_spot (6 commit!) → 1 HIGH/8 LOW.
- Profile-aware business implication: single-maintainer = "structural"
  dili; team = "3-5 weeks delivery slowdown"; multi-org = rakam ağırlıklı.

**Kayıtta kalan 3 saha zayıflığı (sonraki minor patch adayları):**
- Z1: Fragile Velocity pattern 5/5 repoda tetiklemedi — 3/4 axis
  threshold çok agresif olabilir. cline / n8n gibi pattern üreten
  repolar bu cohort'ta yoktu; doğrulamak için ayrı saha turu gerek.
- Z2: kubernetes AI Readiness 0/F yanlış pozitif. K8s'in `OWNERS`,
  `OWNERS_ALIASES`, `keps/` (KEP — enhancement proposals)
  AI-readiness pattern listesinde yok. Detector pattern'leri
  genişletilmeli.
- Z3: openpy Correction 0/F muhtemelen release-pipeline artefaktı —
  CHANGELOG-only commit'leri "fix" kategorisine girip 100% file'a
  yansıyor. Commit intent classifier'a "release-only" filter aday.

**Embarrassment-free pass:** 0.0.5d-öncesi gözlenen "Release Robot
headline", "Diversify .github/docs/tests", "Critical panik kelimesi",
"1262 file pair-program" hatalarından hiçbiri 5 repoda tekrarlamıyor.

## [0.0.9] — 2026-05-17 (Pre-alpha)

The "Fragile Velocity pattern detector" release. The signature pattern
of organizational survivability — and the first of a family. Composite-
signal recognition is the asset no single-metric competitor can copy
without first carrying all the underlying signals.

### New
- **Pattern engine** (`src/blindspot/patterns/`) — new package for
  composite signal detection. ``PatternHit`` dataclass, ``PatternSeverity``
  enum, ``detect_all_patterns()`` registry.
- **Fragile Velocity detector** (`patterns/fragile_velocity.py`) — fires
  when ≥ 3 of these 4 axes trigger:
    * **concentration** — ≥ 5 critical files at ≥ 80% single-owner
    * **low_diversity** — ≥ 2 rubber-stamp files
    * **correction** — ≥ 3 high-correction-load files
    * **ai_gap** — ≥ 2 services without operational context
  3 axes ⇒ MEDIUM severity (score 0.75); 4 axes ⇒ HIGH (score 1.0).
- **Patterns detected** report section — composite recognitions get
  their own card grid, separate from single-rule recommendations.
  Empty when no pattern fires, so the noise floor is zero.
- **Executive brief integration** — patterns appear as colour-coded
  tags right under "Top N risks" in the brief.

### Why this matters
Single-metric race is crowded (Datadog, GitClear, Allstacks). Pattern
detection isn't. Fragile Velocity is the first; the engine scaffold
is ready for **Onboarding Trap**, **Review Theatre**, **Knowledge
Cliff** in later releases.

### Tests
- 479 passing (+6 since 0.0.8): Fragile Velocity detector edge cases.

## [0.0.8] — 2026-05-17 (Pre-alpha)

The "Risk dedup + Confidence" release. Same problem mentioned in four
different recommendations now collapses to one compound line; every
recommendation carries a confidence badge so you know when to trust
the headline number.

### New
- **Confidence layer** — `RecommendedAction.confidence` (Confidence enum:
  HIGH / MEDIUM / LOW). New `actions/confidence.py` scoring engine:
  scan-level ceiling driven by commit volume + window + repo profile
  (doc-only ⇒ always LOW); per-action downgrade for review-hygiene
  rules with thin samples (< 5 reviews). Confidence badge in the
  recommendations table.
- **Compound risk merging** — `actions/compound.py` post-processes the
  recommendation list. When the same file/service triggers ≥ 2 rules
  (e.g. bus factor 1 *and* knowledge decay *and* high correction load),
  they collapse to one *Compound concentration* line that names the
  combined risk. Aggregate targets (`(repo)`, `"4 services"`) skip
  collapsing. New `FragilityPattern.COMPOUND_CONCENTRATION`.
- **Recommendations table** now shows a Confidence column alongside
  Priority. Compound rows carry the new pattern badge.

### Tests
- 473 passing (+14 since 0.0.7): 8 confidence, 6 compound.

## [0.0.7] — 2026-05-17 (Pre-alpha)

The "Executive Brief" release. 30-repo saha testi sonrası en yüksek
değer/maliyet düzeltmesi: rapor en başına 1-sayfa CTO-language brief
ekler. Aynı veri, decision-clarity-first sunum.

### New
- **Executive brief block** at the very top of the HTML report — surfaces
  what a CTO needs in 90 seconds: overall resilience band, top 3
  risks (de-duplicated), business implication sentence. Above the
  existing narrative; replaces nothing.
- **Business implication mapper** (`narrative/business_implication.py`)
  — deterministic, profile-aware signal-to-CTO-language translator.
  Priority: delivery cost from departure orphans → multiple
  single-owner services → stability debt → review theatre → AI-
  onboarding gap. EN + TR. Returns `None` when no signal is strong
  enough — silence over hedged sentence.
- **Top-3 risk selector** (`narrative/exec_risks.py`) — weights actions
  by fragility pattern *and* priority (so a MEDIUM
  single-owner-concentration outranks a HIGH plain rec), then
  de-duplicates by target so one service can't crowd out other risks.

### Fixed
- **AI-readiness service granularity** — `AIReadinessEngine.detect()`
  was hard-coded to `top_level_dir()`, ignoring the code-root-aware
  `service_of` factory that bus-factor / decay / departure all use.
  Result: single-package Python repos saw "src" as an AI-readiness
  service in recommendations. Now accepts `service_of` injection like
  the rest of the engines.

### Tests
- 459 passing (+16 since 0.0.6): 8 business_implication, 5 exec_risks,
  3 report (brief render + AI-readiness regression).

## [0.0.6] — 2026-05-17 (Pre-alpha)

The "Phase 2 graph package" release. Four signals that turn the report
from a list of facts into a system-shaped picture, plus a profile
badge in the HTML hero so the band reads correctly at a glance.

### New
- **Knowledge graph** (`resilience/knowledge_graph.py`) — bipartite
  top-N contributors × top-M services Mermaid diagram in the
  *People & Ownership* group. Edges = per-service coverage share;
  thick edges = single-owner concentration. The team-shaped picture
  of where knowledge lives.
- **Hidden silo detection** (`resilience/silos.py`) — flags services
  whose reviewer set never overlaps any other service in the scan.
  Tribal-knowledge clusters. Emits a `REVIEW_HYGIENE` MEDIUM
  recommendation: "Cross-pollinate reviewers for '{service}'".
- **Change Fear Index** (`resilience/change_fear.py`) — new
  "files nobody dares to touch" table in *Knowledge State*: high
  PageRank centrality + few contributors + long-untouched. Different
  from decay: decay is "owner stopped caring", fear is "nobody wants
  to start".
- **Timeline event annotations** (`trend/events.py`) — optional
  `events:` block in `.blindspot.yaml` pins org events (re-orgs,
  layoffs, AI rollouts) to the resilience trend table. Each snapshot
  picks the closest event within 14 days. Lets readers see whether a
  drop coincided with a known organisational change.
- **Profile badge** in the HTML resilience score block — colour-coded
  pill (single-maintainer / founder-led / team / multi-org / doc-only /
  unknown) plus one-line note so the band reads with context, not as a
  panic label.

### Tests
- 443 passing (+17 since 0.0.5e): 4 knowledge graph, 4 silo detection,
  4 change-fear, 5 timeline events.

## [0.0.5e0] — 2026-05-16 (Pre-alpha)

The "boardroom-grade polish" pass. Three quality-of-life refinements
driven by the same saha test cohort — turning surface-level numbers
into concrete, scoped, profile-aware advice.

### New
- **Effort-aware diversification recommendations** —
  `RecommendationContext.service_top_files` is now a tuple of up to 3
  files (was a single string). Service-level diversification advice
  lists those concrete files and adds a cadence hint:
  * services with ≥ 50 files: *"Cadence: one file per sprint to keep
    the load reviewable."*
  * services with ≥ 15 files: *"Cadence: aim to cover the top files
    this quarter."*
  * smaller services: no cadence (no need).
  Turns "1589 files would orphan" into a scoped to-do.
- **Repo profile detection** — new `resilience/profile.py` classifies
  the repo as one of `doc-only` / `single-maintainer` / `founder-led`
  / `team` / `multi-org` / `unknown` from authors, services, file
  count and the dominant author's coverage share.
- **Profile-aware narrator framing** — the executive summary's
  structural-note line is now wired to the profile:
  * `single-maintainer` / `founder-led`: "concentration is structural
    and expected".
  * `doc-only`: "very little code surface for this analysis".
  * `multi-org` + Fragile/Critical band: "concentration signals here
    are real risks, not structural artefacts".
  * `team` / `unknown` with low ownership: previous generic structural
    note (kept as fallback).
  EN + TR.
- **AI-readiness gap aggregation** — `_ai_readiness_gap` no longer
  spams the recommendation table with one LOW line per bare service.
  Compound-risk gaps (low coverage + bus factor ≤ 1) remain
  individual MEDIUM lines; everything else collapses into a single
  LOW line ("Add AI-readable operational context across N services")
  with the service names listed in the description.

### Tests
- 426 passing (+12 since 0.0.5d): 3 effort-aware rec tests, 6 profile
  detection tests, 2 AI-readiness aggregation tests, 1 housekeeping.

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
