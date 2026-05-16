# blindspot

> **Engineering resilience for AI-accelerated teams.**
> Detect hidden organizational fragility — concentrated ownership, shallow
> reviews, knowledge decay, single-engineer dependencies — *before* they
> become delivery risks.

```bash
pip install blindspot
blindspot scan /path/to/repo
```

One self-contained HTML report. No server. No signup. No telemetry.

> 🚧 **Pre-alpha.** APIs and metrics will change.

---

## What you get

**One report, grouped for both audiences.**

`blindspot scan /repo` produces a single HTML file organised under four
headers — **TL;DR** (executive summary, resilience score with A–F grades,
top actions, trend), then **People & Ownership**, **Knowledge State**,
**Process Quality** for drill-down. A board reads the top; an engineering
manager scrolls.

**A specific question, answered.**

```bash
blindspot scan /repo --simulate-departures "alice@x.com,bob@x.com,carol@x.com"
```

> *"If these three engineers leave together after a re-org, how many files
> become orphans, which services take the hit, and what should we do
> first?"*

---

## Why this exists

AI coding tools made engineering teams faster. But faster does not mean
*understood*. Codebases now carry a new kind of risk: services that
shipped quickly, owned by one person, reviewed by no one in depth — and
that one person can leave tomorrow.

**Existing tools measure velocity. blindspot measures resilience.**

The product is built around three rules:

- **Service-first, not person-first.** Default views show service-level risk; person views require service context.
- **Evidence over inference.** Signals come from observable git/PR/filesystem state — not from guessing how someone codes.
- **Reports, not surveillance.** blindspot answers *"is this service fragile?"*, not *"is this person slacking?"*.

---

## What it measures

| Signal | What it tells you |
|---|---|
| **Ownership concentration** | Who actually understands each part of the codebase, weighted by recency and review depth |
| **Bus factor** per service / folder | How many people would need to leave before knowledge is critically lost |
| **Departure simulation** | What happens if a specific person — or a specific *group* — leaves: orphan files, affected services, coverage loss |
| **Knowledge decay** | Code volatility and contributor drift, projected 30 / 60 / 90 days forward |
| **Review lineage** | Where approvals land without substantive comments (rubber-stamp ratio), and where one reviewer carries everything (diversity HHI) |
| **Correction load** | Share of recent commits to each file that are follow-up fixes or reverts — observable evidence of *stability debt*, not a verdict on people |
| **AI-native operational context** | Per-service coverage of agent rules, specs, prompts, architecture decisions and skills. How much organizational memory exists for new humans *and* AI agents to load. **Not** an AI-generated-code detector |
| **Engineering Resilience Score** | Composite 0–100 number + letter grade, with band (Strong / Moderate / Fragile / Critical) |

Each signal that's actionable generates a concrete recommendation in the
**Top actions** table, tagged with the relevant fragility pattern
(`single-owner-concentration`, `review-without-scrutiny`,
`fragile-velocity`).

---

## Quick start

```bash
# Install
pip install blindspot

# Full report (grouped: TL;DR + People · Knowledge · Process)
blindspot scan /path/to/repo --output report.html

# Multi-person departure scenario (combined card at the top)
blindspot scan /path/to/repo \
    --simulate-departures "alice@x.com,bob@x.com"

# Single-person deep-dive
blindspot simulate --person alice@example.com /path/to/repo
```

A **rule-based narrator** ships in the package — the executive summary
is deterministic, in-process, no network, no key required. Configure a
cloud LLM key (Anthropic or OpenAI) for richer prose; the report itself
shows you how.

---

## Documentation

Full end-to-end documentation lives in [docs/](docs/README.md) — the
algorithms (with formulas and parameters), the architecture, the CLI
reference, configuration, and how to read every section of the report.

---

## Roadmap

| Phase | Surface | Status |
|---|---|---|
| 1 | CLI + static HTML report | Shipping |
| 1 | Multi-person departure scenarios | Shipped (0.0.5b) |
| 2 | Knowledge graph visualization | Planned |
| 2 | Hidden silo detection + Change fear index | Planned |
| 3 | GitHub Action + Checks API output | Planned |
| 3 | Self-hosted dashboard | Planned |
| 3 | Slack / Jira / incident integration | Planned |

---

## License

MIT. See [LICENSE](LICENSE).
