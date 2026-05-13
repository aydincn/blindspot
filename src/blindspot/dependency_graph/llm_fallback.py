"""Opt-in LLM extractor for the dependency graph.

When enabled (via `--llm-graph`), this extractor sends the first 200 lines
of each scanned file to a Claude model and asks for a JSON list of
repo-relative file paths the file depends on. The LLM result is unioned
with the static extractor's result (static-first ordering preserved).

This module does NOT run as a silent fallback — it is only invoked when
the user explicitly opts in. Costs are capped by `max_calls` and a
per-file content hash so re-runs hit the cache.

Privacy: only the first 200 lines + a sample of repo paths are sent —
never full file content.
"""

import hashlib
import json
from dataclasses import dataclass, field
from typing import Protocol

from blindspot.dependency_graph.extractors.base import ExtractionContext

DEFAULT_MAX_CALLS = 50
DEFAULT_MAX_LINES = 200
DEFAULT_REPO_SAMPLE = 200


class _Completer(Protocol):
    def complete(self, system: str, user: str) -> str: ...


_SYSTEM = (
    "You analyze source files and identify which other files in the same "
    "repository they directly depend on. You respond with strict JSON only."
)


def _build_user_prompt(
    file_path: str, snippet: str, repo_files_sample: list[str]
) -> str:
    return (
        f"File path: {file_path}\n"
        f"Other repo files (sample): {json.dumps(repo_files_sample)}\n\n"
        f"First lines of the file:\n```\n{snippet}\n```\n\n"
        "Return a JSON array of repo-relative paths (strings) for the files "
        "this file imports/requires/includes from the repo. "
        "Exclude external libraries, stdlib, and packages not present in the "
        "sample. Output JSON array only, no prose."
    )


@dataclass
class LLMImportExtractor:
    client: _Completer
    max_calls: int = DEFAULT_MAX_CALLS
    max_lines: int = DEFAULT_MAX_LINES
    repo_sample_size: int = DEFAULT_REPO_SAMPLE
    calls_made: int = 0
    cache: dict[str, list[str]] = field(default_factory=dict)

    def maybe_extract(
        self,
        file_path: str,
        content: str,
        ctx: ExtractionContext,
        static_result: list[str],
    ) -> list[str]:
        """Run the LLM for this file and union with the static result.

        This method is only invoked when the user opts in via
        `--llm-graph`. It always runs (subject to cache + max_calls cap)
        — there is no static-empty / import-pattern heuristic.
        """
        digest = self._digest(content)
        cached = self.cache.get(digest)
        if cached is not None:
            return self._merge(static_result, cached)
        if self.calls_made >= self.max_calls:
            return static_result

        snippet = "\n".join(content.splitlines()[: self.max_lines])
        sample = sorted(ctx.repo_files)[: self.repo_sample_size]
        user_prompt = _build_user_prompt(file_path, snippet, sample)

        try:
            raw = self.client.complete(_SYSTEM, user_prompt)
        except Exception:
            self.cache[digest] = []
            return static_result
        self.calls_made += 1

        parsed = _parse_response(raw)
        # Keep only paths that actually exist in the repo.
        resolved = [p for p in parsed if p in ctx.repo_files and p != file_path]
        self.cache[digest] = resolved
        return self._merge(static_result, resolved)

    @staticmethod
    def _merge(static_result: list[str], llm_result: list[str]) -> list[str]:
        # Preserve static-first ordering, dedupe while keeping insertion order.
        seen: set[str] = set()
        out: list[str] = []
        for p in list(static_result) + list(llm_result):
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out

    @staticmethod
    def _digest(content: str) -> str:
        return hashlib.sha256(content[:8000].encode("utf-8", errors="replace")).hexdigest()


def _parse_response(raw: str) -> list[str]:
    s = raw.strip()
    if s.startswith("```"):
        s = s.strip("`")
        if s.lower().startswith("json"):
            s = s[4:].lstrip()
        if s.endswith("```"):
            s = s[:-3]
        s = s.strip()
    # Try to extract the outermost JSON array.
    start = s.find("[")
    end = s.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(s[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if isinstance(item, (str, int))]


__all__ = ["DEFAULT_MAX_CALLS", "LLMImportExtractor"]
