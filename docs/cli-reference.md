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
| `--with-reviews` / `--no-reviews` | on (auto) | Auto-fetch PR/review data when credentials are available. The scan never errors on missing credentials — it continues silently and the report shows how to enable. Use `--no-reviews` to skip entirely. |
| `--max-prs` | `50` | Maximum PRs to fetch when review data is being collected. |
| `--github-token` | `""` | GitHub personal access token. Overrides `.blindspot.yaml`. Needed for private repos when the `gh` CLI isn't available. Never read from environment variables. |
| `--bitbucket-username` | `""` | Bitbucket Cloud username (or Atlassian account email for API tokens). Overrides `.blindspot.yaml`. |
| `--bitbucket-app-password` | `""` | Bitbucket Cloud app password OR Atlassian API token with `pullrequest:read` + `repository:read` scopes. Overrides `.blindspot.yaml`. |

GitHub auth precedence: explicit `--github-token` → `gh` CLI (if
installed and authenticated) → anonymous (public repos only).
Bitbucket has no anonymous path — credentials are required.
When `--with-reviews` is auto and no credentials are detected, the
report itself shows the exact setup steps. See
[configuration.md](configuration.md).

### Analysis depth

| Flag | Default | Meaning |
|---|---|---|
| `--experimental-ai-signal` | off | Classify authors by AI-amplification + code-quality signals. Experimental — see [algorithms.md](algorithms.md#10-ai-amplification-detector). |
| `--check-codeowners` / `--no-check-codeowners` | on | Validate the repo's `CODEOWNERS` file (if present) against actual ownership. |
| `--simulate-top-departures` | `6` | Add "what-if departure" scenario cards to the report for the top-N contributors by aggregate coverage. `0` disables it. |

The trend section (resilience snapshots at 90/60/30/0 days ago) is
**always on** — no flag.

### Dependency graph

| Flag | Default | Meaning |
|---|---|---|
| `--no-dependency-graph` | off (graph builds) | Skip building the file-dependency graph. Faster, but recommendations won't be filtered by structural importance, and the backbone/module/central-models sections are absent. |
| `--code-root` | `""` (auto) | Repo-relative directory to constrain the dependency graph to. Auto-detect prefers `src/`, then `lib/`, then `app/`, otherwise repo root. Set to `.` to scan the whole repo. |
| `--include-tests-in-graph` | off | Include files under `tests/`, `examples/`, `docs/` in the dependency graph. Off by default — those folders distort the architectural view. They still count for ownership and decay regardless. |
| `--importance-threshold` | `0.005` | PageRank importance below which a file is excluded from recommendations and display tables. Stops one-shot scripts / leaf utilities generating noise. |

### Narrative

The narrative section is **always on**. Tier-0 is a rule-based,
in-process narrator that produces a deterministic executive summary and
per-recommendation rationales from the report data — no API key
required. For richer prose, configure a cloud LLM:

| Flag | Default | Meaning |
|---|---|---|
| `--narrative-lang` | `en` | Language for the narrative: `en` or `tr`. |
| `--api-key` | `""` | Cloud LLM API key. When set, overrides the rule-based narrator. Overrides `.blindspot.yaml`. |
| `--model` | `""` | LLM model id. Overrides config. |
| `--provider` | `""` | LLM provider — `anthropic` (default) or `openai`. |

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
| `--with-narrative` | off | Add an LLM-generated departure briefing with mitigation steps. (Cloud only — `--api-key` required.) |
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
  review data can be fetched (credentials present) or when an LLM
  `--api-key` is configured. With neither, the report is still complete
  via the rule-based narrator + the in-report upgrade hints.
- **Flags that need credentials:** review fetch (private GitHub repo or
  any Bitbucket repo) and cloud narrative. All read from CLI flags or
  `.blindspot.yaml` — never the environment.
- **Without review credentials:** review-hygiene metrics
  (rubber-stamp ratio, reviewer diversity, approval latency) and the PR
  activity mix cannot be produced. Everything else — ownership, bus
  factor, decay, departure, dependency graph, central models,
  resilience score, trend, narrative (rule-based) — still works on
  local git alone.
- **Conditional report sections:** author profiles appear with
  `--experimental-ai-signal`; trend and narrative appear always. See
  [outputs.md](outputs.md).

---

## See also

- [quickstart.md](quickstart.md) — copy-paste first runs.
- [configuration.md](configuration.md) — `.blindspot.yaml` and auth setup.
- [architecture.md](architecture.md) — which pipeline step each flag toggles.
