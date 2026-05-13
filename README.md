# blindspot

**The bus factor for the AI era.** Map your team's knowledge blindspots before someone leaves.

> 🚧 **Pre-alpha.** Codename: *Blindspot*. APIs and metrics will change.

## Why

AI coding tools made engineering teams faster. But faster does not mean *understood*. Codebases now carry a new kind of risk: services that shipped quickly, owned by one person, reviewed by no one in depth — and that one person can leave tomorrow.

Existing tools measure velocity. **blindspot measures resilience.**

## What it measures

- **Ownership concentration** — who *actually* understands each part of the codebase, weighted by recency and review depth
- **Bus factor** per service / folder — how many people would need to leave before knowledge is critically lost
- **Review lineage** — who reviews what, and where reviewer redundancy is dangerously thin
- **Departure simulation** — *"If two senior devs on Payment leave next month, what coverage do we lose?"*
- **Knowledge decay** — code volatility and contributor drift, projected 30 / 60 / 90 days forward

## Quick start

```bash
pip install blindspot
blindspot scan /path/to/repo --output blindspot_report.html
blindspot simulate --person alice@example.com /path/to/repo
```

Output is a single self-contained HTML file. No server, no signup, no telemetry.

## Design principles

- **Service-first, not person-first.** Default views show service-level risk. Individual views require explicit, justified access.
- **Evidence over inference.** AI-usage signals come from official telemetry (e.g. GitHub Copilot Usage API) when available — not from guessing.
- **Reports, not surveillance.** blindspot answers *"is this service fragile?"*, not *"is this person slacking?"*.

## Roadmap

| Phase | Surface | Status |
|---|---|---|
| 1 | CLI + static HTML report | In progress |
| 1 | GitHub Action + Checks API output | Planned |
| 2 | Self-hosted dashboard | Planned |
| 2 | AI signal layer (Copilot Usage API) | Planned |
| 3 | Slack / Jira / incident integration | Planned |

## License

MIT. See [LICENSE](LICENSE).
