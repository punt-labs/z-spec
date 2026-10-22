""".github/workflows/test.yml, read as text for the ProB cache and pin tests.

The workflow is parsed line-wise rather than with a YAML library: what the
tests gate is the literal text GitHub runs (step order, which shell branch a
command sits in, where a value is defined), and ``#`` comment lines are
dropped first so prose can never satisfy an assertion.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Self, final

_WORKFLOW: Final[Path] = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "test.yml"
)
_JOB_HEADER: Final[re.Pattern[str]] = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$")
_ENV_ENTRY: Final[re.Pattern[str]] = re.compile(r"^      ([A-Z0-9_]+):")
HIT_TEST: Final[str] = 'if [ "${CACHE_HIT}" = "true" ]; then'


@final
@dataclass(frozen=True, slots=True)
class Step:
    """One ``- ...`` entry of a job's steps list, as raw YAML text."""

    text: str

    @classmethod
    def all_in(cls, job: str) -> list[Self]:
        """Split a job's text into its steps."""
        lines = job.splitlines()
        if "    steps:" not in lines:
            raise ValueError("job has no steps:")
        first = lines.index("    steps:") + 1
        marker = " " * (len(lines[first]) - len(lines[first].lstrip())) + "- "
        steps: list[list[str]] = []
        for line in lines[first:]:
            if line.startswith(marker):
                steps.append([line])
            elif steps:
                steps[-1].append(line)
        return [cls("\n".join(s)) for s in steps]

    def field(self, key: str) -> str:
        match = re.search(rf"^\s*(?:- )?{re.escape(key)}: (.*)$", self.text, re.M)
        if match is None:
            raise ValueError(f"step has no {key}: field:\n{self.text}")
        return match.group(1).strip()

    def has(self, needle: str) -> bool:
        return needle in self.text

    def script(self) -> list[str]:
        """Return the step's ``run: |`` body, one stripped line per entry."""
        lines = self.text.splitlines()
        start = next((i for i, ln in enumerate(lines) if ln.strip() == "run: |"), None)
        if start is None:
            raise ValueError(f"step has no `run: |` block:\n{self.text}")
        return [ln.strip() for ln in lines[start + 1 :] if ln.strip()]

    def curl_argv(self) -> list[str]:
        """Return the script's one curl command, up to any ``||`` handler."""
        script = self.script()
        starts = [i for i, ln in enumerate(script) if ln.startswith("curl ")]
        if len(starts) != 1:
            raise ValueError(f"expected one curl command in the step, got {starts}")
        parts: list[str] = []
        i = starts[0]
        while script[i].endswith("\\"):
            parts.append(script[i][:-1])
            i += 1
        parts.append(script[i])
        argv = shlex.split(" ".join(parts))
        return argv[: argv.index("||")] if "||" in argv else argv


@final
@dataclass(frozen=True, slots=True)
class Branch:
    """Line indices of the cache-hit ``if``, its ``else``, and its ``fi``."""

    if_: int
    else_: int
    fi: int

    @classmethod
    def locate(cls, script: list[str]) -> Self:
        """Find the cache-hit if/else/fi by shell nesting, not indentation."""
        if script.count(HIT_TEST) != 1:
            raise ValueError(f"expected one `{HIT_TEST}` line")
        start = script.index(HIT_TEST)
        depth, else_ = 0, None
        for i in range(start, len(script)):
            line = script[i]
            if line.startswith("if ") and line.endswith("then"):
                depth += 1
            elif line == "else" and depth == 1:
                else_ = i
            elif line == "fi":
                depth -= 1
                if depth == 0:
                    if else_ is None:
                        raise ValueError("cache-hit if has no else (miss) branch")
                    return cls(start, else_, i)
        raise ValueError("cache-hit if is never closed by fi")


@final
class Workflow:
    """test.yml with comment lines dropped, split into jobs and steps."""

    __slots__ = ("_raw", "_text")
    _raw: str
    _text: str

    def __new__(cls, path: Path = _WORKFLOW) -> Self:
        self = super().__new__(cls)
        self._raw = path.read_text(encoding="utf-8")
        self._text = "\n".join(
            ln for ln in self._raw.splitlines() if not ln.lstrip().startswith("#")
        )
        return self

    def top_level_keys(self) -> list[str]:
        return re.findall(r"^([A-Za-z_-]+):", self._text, re.M)

    def jobs(self) -> dict[str, str]:
        lines = self._text.splitlines()
        if "jobs:" not in lines:
            raise ValueError("test.yml has no top-level jobs: key")
        jobs: dict[str, list[str]] = {}
        current: list[str] | None = None  # None until the first job header
        for line in lines[lines.index("jobs:") + 1 :]:
            if match := _JOB_HEADER.match(line):
                current = jobs.setdefault(match.group(1), [])
            elif current is not None:
                current.append(line)
        return {name: "\n".join(body) for name, body in jobs.items()}

    def job(self, name: str) -> str:
        return self.jobs()[name]

    def job_env(self, name: str, key: str) -> str:
        """Return a quoted ``key: "value"`` defined exactly once in the job."""
        found = re.findall(rf'^\s+{re.escape(key)}: "([^"]*)"$', self.job(name), re.M)
        if len(found) != 1:
            raise ValueError(f"expected {key} defined once in {name}, got {found}")
        return str(found[0])

    def job_env_keys(self, name: str) -> list[str]:
        """Return the keys of the job-level ``env:`` that precedes ``steps:``."""
        lines = self.job(name).splitlines()
        if "    env:" not in lines or "    steps:" not in lines:
            raise ValueError(f"{name} has no job-level env: or no steps:")
        start, end = lines.index("    env:"), lines.index("    steps:")
        if start > end:
            raise ValueError(f"{name}: env: must precede steps:")
        entries = (_ENV_ENTRY.match(ln) for ln in lines[start + 1 : end])
        return [m.group(1) for m in entries if m]

    def steps(self, name: str) -> list[Step]:
        return Step.all_in(self.job(name))

    def step(self, job: str, needle: str) -> tuple[int, Step]:
        """Return the one step of ``job`` containing ``needle``, with its index."""
        hits = [(i, s) for i, s in enumerate(self.steps(job)) if s.has(needle)]
        if len(hits) != 1:
            raise ValueError(f"expected exactly one {job} step with {needle!r}")
        return hits[0]
