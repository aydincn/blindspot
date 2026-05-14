# Quickstart

Get a knowledge-resilience report out of a repo in under five minutes.

---

## Requirements

- Python **3.11+**
- A local git repository to scan (Blindspot reads git history; the repo
  must have at least one commit)

## Install

From a clone of the Blindspot repo:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e .
```

For the optional LLM features (`--with-narrative`, `--llm-graph`), add
the `ai` extra:

```bash
.venv/bin/pip install -e ".[ai]"
```

This puts a `blindspot` command on your PATH (inside the venv). The rest
of this page assumes you run it as `.venv/bin/blindspot` — drop the
prefix if your venv is activated.

---

## First run — a plain scan

```bash
.venv/bin/blindspot scan /path/to/repo --output report.html
```

This is **fully offline**. It reads the git log for the last 180 days
and writes `report.html`. You get:

- the Engineering Resilience Score
- service- and file-level bus factor
- knowledge decay with 30/60/90-day projections
- the dependency graph: structural backbone, central models, module map
- top-3 departure scenarios
- a prioritised recommendations list

Open the file in any browser:

```bash
open report.html        # macOS
xdg-open report.html    # Linux
```

There is no server and no signup — `report.html` is a complete,
standalone file you can email.

## Add review data

To get review-hygiene metrics (rubber-stamp ratio, reviewer diversity,
approval latency) and the PR activity mix, add `--with-reviews`. The
remote is auto-detected:

```bash
.venv/bin/blindspot scan /path/to/repo --with-reviews --output report.html
```

- **GitHub public repo** — works anonymously (60 requests/hour), or
  better via the `gh` CLI if you have it (`gh auth login`).
- **GitHub private repo** — needs the `gh` CLI authenticated, or a
  `--github-token`.
- **Bitbucket Cloud** — needs `--bitbucket-username` +
  `--bitbucket-app-password` (or a `bitbucket:` block in
  `.blindspot.yaml`).

See [configuration.md](configuration.md) for credential setup.

## Simulate a departure

The focused "what do we lose if this person leaves" report:

```bash
.venv/bin/blindspot simulate -p alice@example.com /path/to/repo
```

Writes `blindspot_departure.html` — impact summary, per-service impact,
the files that would become orphans, and a ranked list of potential
successors. Repeat `-p` to simulate several people leaving together:

```bash
.venv/bin/blindspot simulate -p alice@example.com -p bob@example.com /path/to/repo
```

## Try it on the synthetic demo

The repo ships a synthetic example you can scan without needing a real
project:

```bash
.venv/bin/python examples/synthetic_demo.py
```

---

## What next

- **Reading the report** — [outputs.md](outputs.md) explains every
  section.
- **Understanding a number** — [algorithms.md](algorithms.md) has the
  formula behind each metric.
- **All the flags** — [cli-reference.md](cli-reference.md).
- **Review data / LLM setup** — [configuration.md](configuration.md).
- **How it all fits together** — [architecture.md](architecture.md).
