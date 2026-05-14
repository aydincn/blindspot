# CLI Reference

Blindspot has three commands: `scan`, `simulate`, and `version`.

```
blindspot scan      [OPTIONS] [PATH]   # full repo health report
blindspot simulate  [OPTIONS] [PATH]   # focused "what if X leaves" report
blindspot version                      # print the version
```

`PATH` defaults to `.` (current directory) for both `scan` and
`simulate`.

---

## `blindspot scan`

Scans a repository and generates a knowledge-risk HTML report.

```
blindspot scan /path/to/repo --output report.html
```

### Core

| Flag | Default | Meaning |
|---|---|---|
| `PATH` (argument) | `.` | Repository path to scan. |
| `--output`, `-o` | `blindspot_report.html` | HTML report output path. |
| `--since-days` | `180` | Analysis window in days. Everything (commits, ownership, decay, AI signal) is scoped to this window. |
| `--include-merges` | off | Include merge commits in the analysis. Off by default — merge commits inflate counts without representing authored work. |

### Review data + authentication

| Flag | Default | Meaning |
|---|---|---|
| `--with-reviews` | off | Fetch PR/review data. Auto-detects GitHub or Bitbucket Cloud from the git remote. Without it, review-hygiene and PR-mix sections are simply absent. |
| `--max-prs` | `50` | Maximum PRs to fetch when `--with-reviews` is set. |
| `--github-token` | `""` | GitHub personal access token. Overrides `.blindspot.yaml`. Needed for private repos when the `gh` CLI isn't available. Never read from environment variables. |
| `--bitbucket-username` | `""` | Bitbucket Cloud username. Overrides `.blindspot.yaml`. Never read from environment variables. |
| `--bitbucket-app-password` | `""` | Bitbucket Cloud app password with `pullrequest:read` + `repository:read` scopes. Overrides `.blindspot.yaml`. |

GitHub auth precedence: explicit `--github-token` → `gh` CLI (if
installed and authenticated) → anonymous (60/hr, public repos only).
Bitbucket has no anonymous path — credentials are required for
`--with-reviews` on a Bitbucket remote. See
[configuration.md](configuration.md).

### Analysis depth

| Flag | Default | Meaning |
|---|---|---|
| `--experimental-ai-signal` | off | Classify authors by AI-amplification + code-quality signals. Experimental — see [algorithms.md](algorithms.md#10-ai-amplification-detector). |
| `--with-trend` | off | Compute resilience snapshots at 90/60/30/0 days ago for the trend view. Slower (re-runs the pipeline four times). |
| `--check-codeowners` / `--no-check-codeowners` | on | Validate the repo's `CODEOWNERS` file (if present) against actual ownership. |
| `--simulate-top-departures` | `3` | Add "what-if departure" scenario cards to the report for the top-N contributors by aggregate coverage. `0` disables it. |

### Dependency graph

| Flag | Default | Meaning |
|---|---|---|
| `--no-dependency-graph` | off (graph builds) | Skip building the file-dependency graph. Faster, but recommendations won't be filtered by structural importance, and the backbone/module/central-models sections are absent. |
| `--code-root` | `""` (auto) | Repo-relative directory to constrain the dependency graph to. Auto-detect prefers `src/`, then `lib/`, then `app/`, otherwise repo root. Set to `.` to scan the whole repo. |
| `--include-tests-in-graph` | off | Include files under `tests/`, `examples/`, `docs/` in the dependency graph. Off by default — those folders distort the architectural view. They still count for ownership and decay regardless. |
| `--importance-threshold` | `0.005` | PageRank importance below which a file is excluded from recommendations and display tables. Stops one-shot scripts / leaf utilities generating noise. |

### LLM graph resolution

| Flag | Default | Meaning |
|---|---|---|
| `--llm-graph` | off | Use an LLM to resolve imports for every scanned file and union the result with the static extractor. Opt-in only. Requires the same API config as `--with-narrative`. |
| `--llm-graph-max-calls` | `50` | Cap on LLM calls during `--llm-graph` — a cost guard. |

### LLM narrative

| Flag | Default | Meaning |
|---|---|---|
| `--with-narrative` | off | Add an LLM-generated executive summary, headline action, and per-recommendation rationales on top of the report. |
| `--narrative-lang` | `en` | Language for the LLM narrative: `en` or `tr`. |
| `--api-key` | `""` | LLM API key. Overrides `.blindspot.yaml`. |
| `--model` | `""` | LLM model id. Overrides config. |
| `--provider` | `""` | LLM provider. Defaults to `anthropic`. |

---

## `blindspot simulate`

Simulates the impact of one or more people departing — a focused
"what do we lose if X leaves" HTML report.

```
blindspot simulate -p alice@example.com /path/to/repo
blindspot simulate -p alice@example.com -p bob@example.com /path/to/repo
```

| Flag | Default | Meaning |
|---|---|---|
| `PATH` (argument) | `.` | Repository path. |
| `--person`, `-p` | *(required)* | Person email. Repeat the flag to simulate multiple people leaving together. |
| `--since-days` | `180` | Analysis window in days. |
| `--output`, `-o` | `blindspot_departure.html` | HTML report output path. Set to an empty string to skip writing a file (console output only). |
| `--with-narrative` | off | Add an LLM-generated departure briefing with mitigation steps. |
| `--narrative-lang` | `en` | Language for the LLM narrative: `en` or `tr`. |
| `--api-key` | `""` | LLM API key. |
| `--model` | `""` | LLM model id. |
| `--provider` | `""` | LLM provider. |

The `simulate` report always includes: an impact summary, per-service
impact, the orphaned files, the heavily-impacted files, and the ranked
"potential successors" who would inherit the orphaned work. See
[outputs.md](outputs.md#the-departure-report).

---

## `blindspot version`

Prints the installed Blindspot version. No options.

---

## Notes

- **A plain `scan` is fully offline.** The network is only touched when
  `--with-reviews`, `--with-narrative`, or `--llm-graph` is set.
- **Flags that need credentials:** `--with-reviews` (on a private repo
  or a Bitbucket remote), `--with-narrative`, `--llm-graph`. All read
  from CLI flags or `.blindspot.yaml` — never the environment.
- **Without `--with-reviews`:** review-hygiene metrics
  (rubber-stamp ratio, reviewer diversity, approval latency) and the PR
  activity mix cannot be produced. Everything else — ownership, bus
  factor, decay, departure, dependency graph, central models,
  resilience score — still works on local git alone.
- **Conditional report sections:** several `scan` sections only appear
  when their flag is set (trend → `--with-trend`, author profiles →
  `--experimental-ai-signal`, narrative → `--with-narrative`, etc.).
  See [outputs.md](outputs.md).

---

## See also

- [quickstart.md](quickstart.md) — copy-paste first runs.
- [configuration.md](configuration.md) — `.blindspot.yaml` and auth setup.
- [architecture.md](architecture.md) — which pipeline step each flag toggles.
