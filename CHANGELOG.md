# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
