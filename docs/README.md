# Blindspot Documentation

**Blindspot** is the bus factor for the AI era — a static analysis tool
that maps where a team's engineering knowledge is thin, concentrated, or
decaying, and produces a single self-contained HTML report. No server,
no database, no telemetry.

This folder is the complete reference. The goal: after reading it, no
question marks remain about what Blindspot does, how it computes any
number, or how to read its output.

---

## Contents

| Document | What's in it |
|---|---|
| [overview.md](overview.md) | The problem Blindspot solves, the design principles, the full capability matrix, and the honest limitations. |
| [quickstart.md](quickstart.md) | Install and get your first report out in five minutes. |
| [architecture.md](architecture.md) | The 13 modules, how data flows between them, and the exact step order of the `scan` and `simulate` pipelines. |
| [algorithms.md](algorithms.md) | The core reference — every one of the ~17 algorithms with its exact formula, every parameter and threshold, and the output type. |
| [cli-reference.md](cli-reference.md) | Every command and every flag, with defaults and meanings. |
| [configuration.md](configuration.md) | The `.blindspot.yaml` file, credential precedence, and GitHub / Bitbucket integration setup. |
| [outputs.md](outputs.md) | Every section of the HTML report explained — what it shows, how to read it, which algorithm feeds it. |
| [glossary.md](glossary.md) | One-line definitions of every term. |

---

## Read in this order

**If you're new to Blindspot:**
1. [overview.md](overview.md) — understand what it is and why.
2. [quickstart.md](quickstart.md) — run it once.
3. [outputs.md](outputs.md) — read the report you just generated.

**If you want to understand a specific number:**
- [algorithms.md](algorithms.md) — find the metric, read its formula
  and parameters.
- [glossary.md](glossary.md) — if a term is unfamiliar.

**If you're setting up review data or the LLM features:**
- [configuration.md](configuration.md) — config file + auth.
- [cli-reference.md](cli-reference.md) — the relevant flags.

**If you're working on the code:**
- [architecture.md](architecture.md) — module map and pipelines.
- [algorithms.md](algorithms.md) — every formula traced to its source
  file and line.

---

## Conventions

- Every formula in [algorithms.md](algorithms.md) is traced to a source
  file (and often a line number) so it can be re-verified against the
  code if it ever drifts.
- "Parameters" tables list the dataclass default — the value you get
  unless you override it.
- Sections marked *(only with `--flag`)* in [outputs.md](outputs.md) are
  conditional on a CLI flag.

---

*Documentation for Blindspot 0.0.1 (pre-alpha). The CLI surface and
metrics will change; this folder is kept in sync with the code.*
