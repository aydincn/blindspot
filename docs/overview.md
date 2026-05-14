# Overview

## The problem

AI coding tools made engineering teams faster. But *faster* is not the
same as *understood*. Code now ships quickly, owned by one person,
reviewed by no one in depth — and that one person can leave tomorrow.

Existing developer tools measure **velocity**: lead time, cycle time,
PR throughput, DORA metrics. None of them measure what happens to
**organizational knowledge** while velocity climbs:

- The number of people who actually understand a service goes down.
- Reviews become "approved, no comments" — a stamp, not scrutiny.
- A growing share of the codebase has exactly one person who could
  explain why it is the way it is.

Blindspot measures that second thing. It is the **bus factor for the AI
era**: a static analysis tool that maps where your team's knowledge is
thin, concentrated, or decaying — and tells you concretely what would
break if specific people left.

## What it is

A single-process command-line tool. Point it at a local git repository
and it produces one self-contained HTML report. No server, no database,
no signup, no telemetry. A plain run is fully offline; it only reaches
the network if you explicitly ask for hosting-provider review data or
LLM narrative.

```
blindspot scan /path/to/repo --output report.html
```

## Design principles

These are not aspirations — they are constraints visible in the code.

- **Service-first, not person-first.** The default views are
  service- and file-level risk ("is this service fragile?"), not
  individual scorecards ("is this person slacking?"). Individual data
  appears only where it is unavoidable and is framed as risk, never
  as performance.
- **Reports, not surveillance.** Every output answers a structural
  question. The AI-signal layer is explicitly *experimental* and its
  evidence weight is a confidence multiplier, never a punishment.
- **One process, one file out.** `pip install`, run, get an HTML file
  you can email. No infrastructure to stand up.
- **Credentials never from environment variables.** API keys and
  tokens come only from CLI flags or a `.blindspot.yaml` file — a
  deliberate choice so a scan can't silently pick up an unrelated key
  sitting in a shell. See [configuration.md](configuration.md).
- **Evidence over inference.** Where a real signal exists (git history,
  official PR APIs), Blindspot uses it. Where it would have to guess
  (e.g. "is this commit AI-generated?"), it does not — it measures
  *behavioural consequences* instead.

## Capabilities

What Blindspot can tell you, the algorithm behind it, and where the
answer shows up. Full algorithm detail in
[algorithms.md](algorithms.md); full output detail in
[outputs.md](outputs.md).

| Capability | Question it answers | Powered by | Appears in |
|---|---|---|---|
| **Knowledge map** | Who actually understands each file? | Ownership / coverage scoring | Service risk map, single-ownership files |
| **Bus factor** | How many people could we lose before a service is critically thin? | Bus factor algorithm | Service risk map, resilience score |
| **Knowledge decay** | Which files are going stale — owner gone, others still changing them? | Knowledge decay + 30/60/90-day projection | Knowledge decay section |
| **Departure simulation** | If X leaves tomorrow, what becomes orphaned? | Departure simulation | Departure scenarios (scan), full `simulate` report |
| **Structural backbone** | Which files does everything else depend on? | Dependency graph + PageRank | Structural backbone, module dependency map |
| **Central models** | Which data types is the rest of the code bound to? | AST model detection | Central models section |
| **Review hygiene** | Is review real, or a rubber stamp by the same one person? | Review graph (rubber-stamp ratio, diversity, latency) | Review lineage section |
| **AI-amplification signal** | Whose recent activity shape shifted sharply vs their own baseline? | AI detector + quality signal + profiler *(experimental)* | Author signal profiles |
| **Resilience score** | One number a non-technical stakeholder can track | Composite resilience score | Engineering Resilience Score |
| **Trend** | Is resilience improving or degrading? | Trend engine (past snapshots) | Resilience trend section |
| **CODEOWNERS validation** | Does the declared `CODEOWNERS` match reality? | CODEOWNERS validator | CODEOWNERS validation section |
| **Recommendations** | What should we actually do about all this? | Recommendation engine (7 rules + fragility patterns) | Recommended actions section |
| **PR activity mix** | How much of the throughput is real feature work vs noise? | Diff classifier | PR activity mix section |

## Fragility patterns

Three named failure modes the recommendation engine tags when it sees
them — the AI-era shapes of organizational risk:

- **Review without scrutiny** — approvals land without substantive
  review (high rubber-stamp ratio, or approvals faster than anyone
  could have read the diff).
- **Single-owner concentration** — an entire service rests on one
  person's coverage.
- **Velocity without review** — output spiked, code-quality risk rose,
  and review depth did not keep up.

## Limitations and assumptions

Be honest about what the numbers are and are not:

- **Coverage is a weighted proxy, not ground truth.** It is computed
  from commit recency, volume, and review activity — a good signal for
  "who would I ask about this file", not a measurement of comprehension.
- **Ten of eleven language extractors are regex-based.** Only Python is
  AST-parsed (with inheritance edges and model detection). The others
  (JS/TS, C#/F#, Java, Kotlin, Go, Rust, C/C++, Ruby, PHP, Swift)
  resolve imports heuristically — they err toward missing an edge
  rather than inventing one. `--llm-graph` can fill gaps at a cost.
- **Local git cannot see review data.** Rubber-stamp ratio, reviewer
  diversity, approval latency, and PR categorization all require
  `--with-reviews` and a GitHub or Bitbucket Cloud remote with
  credentials. Without it, those sections are simply absent — the rest
  of the report still works.
- **The AI-signal layer is experimental.** It is behind
  `--experimental-ai-signal`, compares an author only to *their own*
  history, and detects an activity-shape shift — not AI authorship.
  Treat `FAKE_VELOCITY` as "worth a closer look", not a verdict.
- **`scan` analyzes a window.** Everything is scoped to `--since-days`
  (default 180). A repo's deep history is not considered unless you
  widen the window.

## Where to go next

- New here? → [quickstart.md](quickstart.md)
- Want to understand a specific number? → [algorithms.md](algorithms.md)
- Reading a report? → [outputs.md](outputs.md)
- Setting up review data / LLM? → [configuration.md](configuration.md)
