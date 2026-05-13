# Contributing

Thanks for your interest in blindspot. This project is in pre-alpha — APIs,
metrics, and CLI surface will change. Small, focused contributions are very
welcome.

## Dev setup

```bash
python3.11 -m venv .venv
.venv/bin/pip install -e ".[dev,ai]"
```

The `dev` extra pulls in `pytest`, `pytest-cov`, `ruff`, and `mypy`. The
`ai` extra pulls in `litellm` for the optional LLM features.

## Running the tests

```bash
.venv/bin/pytest -q
```

Tests are deterministic and run against synthetic git repositories built
in-memory (see `tests/conftest.py`). They do not hit the network or any
real LLM provider.

For type checks and lint:

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
```

## Submitting changes

- Keep PRs focused on a single concern. Mixing a bug fix with a refactor
  makes review and bisection harder.
- Add a test for any behaviour change. Reproduce the bug or feature in a
  failing test first when you can.
- Update `CHANGELOG.md` if your change is user-visible (new flag, new
  recommendation rule, breaking output).
- Update the README only when the change affects documented usage.

## API keys

Blindspot deliberately does **not** read API keys from environment
variables. Configure providers via:

- `./.blindspot.yaml` (project, in your CWD)
- `~/.config/blindspot/config.yaml` (user)
- CLI flags (`--api-key`, `--model`, `--provider`)

Never commit a real key. `.blindspot.yaml` is already in `.gitignore`;
use `.blindspot.yaml.example` as a template.

## Reporting issues

Use GitHub Issues. Include:
- The exact command you ran.
- The repo characteristics that matter (rough size, languages, whether
  CODEOWNERS or `--with-reviews` was involved).
- The actual output and what you expected.

If you suspect a privacy issue (e.g. raw author identifiers in a place
they shouldn't be), please flag it explicitly so it can be triaged ahead
of other reports.
