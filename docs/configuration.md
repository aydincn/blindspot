# Configuration & Integrations

Blindspot reads optional configuration from a `.blindspot.yaml` file.
It is only needed for the network-touching features: LLM narrative,
LLM graph resolution, and review data (`--with-reviews`). A plain
`scan` needs no configuration at all.

---

## The `.blindspot.yaml` file

A single YAML file with up to three independent blocks:

```yaml
# LLM narrative (--with-narrative, --llm-graph)
narrative:
  provider: anthropic
  model: claude-sonnet-4-6        # optional; defaults to claude-haiku-4-5
  api_key: sk-ant-...

# GitHub review data (--with-reviews on a github.com remote)
github:
  token: ghp_...

# Bitbucket Cloud review data (--with-reviews on a bitbucket.org remote)
bitbucket:
  username: your-bitbucket-username
  app_password: ATBB...
```

You only need the blocks for the features you use. A copyable template
ships as `.blindspot.yaml.example` in the repo root.

---

## Precedence

Every credential is resolved in this order — the first source that
provides a value wins:

1. **Explicit CLI flag** — `--api-key`, `--model`, `--provider`,
   `--github-token`, `--bitbucket-username`, `--bitbucket-app-password`.
2. **CWD config** — `./.blindspot.yaml`, relative to where you *invoke*
   blindspot from.
3. **Scanned-repo config** — `<repo>/.blindspot.yaml`, inside the
   repository being scanned (only consulted if it differs from the CWD).
4. **User config** — `~/.config/blindspot/config.yaml`.

This is the same logic in all three config loaders:
`narrative/config.py`, `collector/github/config.py`,
`collector/bitbucket/config.py`.

## Credentials are never read from environment variables

This is deliberate. A scan must never silently pick up an unrelated API
key or token that happens to be exported in the shell. If a credential
is not on the command line or in a `.blindspot.yaml`, the corresponding
feature is skipped with a clear message — it does not fall back to the
environment.

Practical consequences:
- Put your personal key in `~/.config/blindspot/config.yaml` once.
- Or put a project-specific key in `./.blindspot.yaml` — and keep that
  file out of version control (it is in the repo's `.gitignore`).
- For one-off runs or CI, pass the flag directly.

---

## The scoring config

The ownership and decay algorithm weights (see
[algorithms.md](algorithms.md)) live in `src/blindspot/config.py` as
Pydantic models with baked-in defaults. They are loadable from a YAML
but are not wired to a CLI flag — for normal use the defaults are what
you get. Editing them is an advanced, source-level customization.

| Block | Keys (defaults) |
|---|---|
| `scoring.ownership` | `commit 0.30`, `volume 0.20`, `recency 0.35`, `review 0.15`, `decay_lambda 0.01` |
| `scoring.decay` | `volatility 0.55`, `absence 0.45`, `critical_threshold 0.75`, `high_threshold 0.50`, `medium_threshold 0.25`, `prediction_days [30, 60, 90]` |
| `analysis` | `since_days 180`, `baseline_months 12` |

---

## GitHub integration

When `--with-reviews` is set and the git remote points at
`github.com`, Blindspot fetches PR + review + comment + file data via
the GitHub REST API.

**Remote detection.** `detect_github_remote()` parses the `origin` URL —
HTTPS, SSH, and `ssh://` forms of `github.com/<owner>/<repo>` are all
recognised.

**Auth precedence** (`make_github_client()`):
1. **Explicit token** — `--github-token` or `github.token` in
   `.blindspot.yaml`. Used directly. Required for private repos when
   `gh` is not available.
2. **`gh` CLI** — if the GitHub CLI is installed and authenticated
   (`gh auth login`), Blindspot routes calls through `gh api`, using its
   credentials and its 5000/hr rate limit. Works for private repos the
   `gh` user can access.
3. **Anonymous** — no token, no `gh`: 60 requests/hour, **public repos
   only**.

An explicit token wins over `gh` so behaviour is predictable in CI
where both might be present.

**PAT scopes.** A classic personal access token needs the `repo` scope
for private repos. A fine-grained PAT needs *Pull requests: read* +
*Contents: read* on the target repositories.

---

## Bitbucket Cloud integration

When `--with-reviews` is set and the git remote points at
`bitbucket.org`, Blindspot fetches PR data via the Bitbucket Cloud REST
API v2.0.

**Remote detection.** `detect_bitbucket_remote()` parses the `origin`
URL — HTTPS (including the `user@bitbucket.org` form), SSH, and
`ssh://` forms of `bitbucket.org/<workspace>/<repo>` are recognised.
Self-hosted **Bitbucket Server / Data Center is intentionally not
matched** — it has a different API.

**Auth.** Bitbucket has no useful anonymous access, so `--with-reviews`
on a Bitbucket remote *requires* credentials:
- `bitbucket.username` + `bitbucket.app_password` in `.blindspot.yaml`,
  or
- `--bitbucket-username` + `--bitbucket-app-password` on the command
  line.

Create an app password at **Bitbucket → Personal settings → App
passwords** with the `pullrequest:read` and `repository:read` scopes.
Authentication is HTTP Basic (`username:app_password`).

**Endpoints used** (under
`/2.0/repositories/{workspace}/{repo}/pullrequests`): the PR list, then
per PR `/activity` (→ approvals and change-requests), `/comments`
(→ review comments), and `/diffstat` (→ per-file churn). These are
mapped into the same provider-agnostic `PullRequest` objects the GitHub
collector produces, so everything downstream is identical.

---

## What needs review data vs what doesn't

| Works on local git alone | Needs `--with-reviews` (+ a recognised remote + creds) |
|---|---|
| Ownership / coverage | Rubber-stamp ratio |
| Bus factor (file + service) | Reviewer diversity |
| Knowledge decay + projections | Approval latency |
| Departure simulation | PR activity mix / diff classification |
| Dependency graph + PageRank + central models | Review term of the ownership score |
| Resilience score (ownership + decay sub-scores) | Resilience score (review sub-score) |
| Trend | — |
| CODEOWNERS validation | — |
| AI-amplification signal (`--experimental-ai-signal`) | Quality signal's PR-derived components |
| Recommendations (the non-review rules) | Recommendations (rubber-stamp, diversity, fast-approval rules) |

If review data is unavailable, those sections are simply absent from
the report — nothing errors out.

---

## See also

- [cli-reference.md](cli-reference.md) — every credential flag.
- [quickstart.md](quickstart.md) — first-run setup.
- [overview.md](overview.md#design-principles) — why credentials are
  never read from the environment.
