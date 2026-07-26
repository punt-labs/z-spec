"""Git queries the ratchet needs: base resolution, diffs, and blob reads."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Self

_TIMEOUT = 10


class GitError(Exception):
    """A git command the ratchet depends on failed.

    Raised instead of degrading to a benign default, so an enforcement gate
    fails closed: a failed ``git diff`` can never masquerade as "no changes".
    """


@dataclass(frozen=True, slots=True)
class Diff:
    """Files changed across a commit range, with rename provenance.

    ``renames`` maps a new path to the old path it was renamed from, so a
    renamed file can inherit its predecessor's baseline entry (S8).
    """

    touched: frozenset[str]
    renames: dict[str, str] = field(default_factory=dict)

    def python_files(self) -> frozenset[str]:
        """Return the touched paths that are Python modules."""
        return frozenset(p for p in self.touched if p.endswith(".py"))


class GitRepo:
    """Answer the ratchet's git questions, or degrade to ``None`` outside git."""

    _root: Path | None

    BASELINE_FILE: str = ".oo-baseline.json"
    AUDIT_FILE: str = ".oo-audit.jsonl"

    def __new__(cls, start: Path | None = None) -> Self:
        self = super().__new__(cls)
        self._root = cls._discover_root(start if start is not None else Path.cwd())
        return self

    @property
    def root(self) -> Path | None:
        """Return the repository root, or ``None`` when not inside a repo."""
        return self._root

    @property
    def available(self) -> bool:
        """Return whether git commands can run against a repository."""
        return self._root is not None

    @classmethod
    def _discover_root(cls, start: Path) -> Path | None:
        out = cls._run(["git", "rev-parse", "--show-toplevel"], cwd=start)
        return Path(out.strip()) if out is not None else None

    @staticmethod
    def _run(args: list[str], cwd: Path | None) -> str | None:
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                cwd=cwd,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout

    def _git(self, args: list[str]) -> str | None:
        if self._root is None:
            return None  # not in a repo: degrade, never run against the ambient CWD
        return self._run(["git", *args], cwd=self._root)

    def short_head(self) -> str | None:
        """Return the abbreviated HEAD commit hash."""
        out = self._git(["rev-parse", "--short", "HEAD"])
        return out.strip() if out is not None else None

    def resolve_ref(self, ref: str) -> str | None:
        """Return the full commit hash for a ref, or ``None`` if unresolvable."""
        out = self._git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
        return out.strip() if out else None

    def merge_base(self, left: str, right: str) -> str | None:
        """Return the merge-base commit of two refs, or ``None``."""
        out = self._git(["merge-base", left, right])
        return out.strip() if out else None

    def resolve_base(self, base_ref: str | None) -> str | None:
        """Resolve the comparison base: explicit ref, else merge-base of main.

        Returns the base commit hash, or ``None`` when no base can be
        determined (caller decides bootstrap vs. hard-fail).
        """
        if base_ref is not None:
            return self.resolve_ref(base_ref)
        return self.merge_base("origin/main", "HEAD")

    def diff(self, base: str) -> Diff:
        """Return files changed from ``base`` to the work tree, with renames.

        Diffing against the work tree (not ``base..HEAD``) keeps the touched
        set consistent with the scored tree: identical to ``base..HEAD`` in a
        clean checkout (CI), and inclusive of a developer's tracked
        pre-commit edits locally.
        """
        out = self._git(["diff", "--name-status", "-M", base])
        if out is None:
            msg = f"git diff against {base} failed"
            raise GitError(msg)
        touched: set[str] = set()
        renames: dict[str, str] = {}
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            status = parts[0]
            if status.startswith(("R", "C")) and len(parts) >= 3:
                old, new = parts[1], parts[2]
                touched.add(new)
                if status.startswith("R"):
                    renames[new] = old
            elif len(parts) >= 2:
                touched.add(parts[1])
        return Diff(frozenset(touched), renames)

    def show_baseline(self, ref: str) -> dict[str, dict[str, float]] | None:
        """Return the baseline JSON committed at ``ref``, or ``None`` if absent.

        ``None`` means the blob genuinely does not exist at that ref — the
        first-adoption case. A real git error (bad ref, timeout, infra) raises
        ``GitError`` rather than masquerading as absence, so the gate never
        fails open on a broken git call.
        """
        out = self._show_file(ref, self.BASELINE_FILE)
        if out is None:
            return None
        try:
            loaded = json.loads(out)
        except json.JSONDecodeError as exc:
            msg = f"corrupt baseline blob at {ref}:{self.BASELINE_FILE}: {exc}"
            raise GitError(msg) from exc
        if not isinstance(loaded, dict):
            msg = f"non-dict baseline blob at {ref}:{self.BASELINE_FILE}"
            raise GitError(msg)
        # Each value must be a per-metric dict. A non-dict value (e.g. a string)
        # passes the top-level check but makes ``metric not in entry`` a substring
        # test that silently skips every metric -- a fail-OPEN. Reject it here.
        if not all(isinstance(v, dict) for v in loaded.values()):
            blob = f"{ref}:{self.BASELINE_FILE}"
            raise GitError(f"non-dict entry in baseline blob at {blob}")
        # Each metric value must be a real number. A bool (`true`) is an int
        # subclass that would compare as 0/1 (fail-open); a string would raise
        # TypeError in the comparison. Reject both here so the gate fails closed.
        if not all(
            isinstance(m, (int, float)) and not isinstance(m, bool)
            for entry in loaded.values()
            for m in entry.values()
        ):
            blob = f"{ref}:{self.BASELINE_FILE}"
            raise GitError(f"non-numeric metric in baseline blob at {blob}")
        parsed: dict[str, dict[str, float]] = loaded
        return parsed

    def show_audit(self, ref: str) -> str | None:
        """Return the audit-log text committed at ``ref``, or ``None`` if absent.

        ``None`` means the blob genuinely does not exist at that ref (no base
        history); a real git error raises ``GitError`` rather than silently
        reading as "no base relaxations" and over-waiving.
        """
        return self._show_file(ref, self.AUDIT_FILE)

    def _show_file(self, ref: str, path: str) -> str | None:
        """Return ``git show <ref>:<path>`` text, ``None`` if the path is absent.

        Distinguishes a path missing at an otherwise-readable ref (return
        ``None`` — trusted) from any other failure (raise ``GitError`` —
        fail closed). The callers always pass an already-resolved ref, so a
        non-absence failure is an anomaly, not a benign "no blob".
        """
        if self._root is None:
            return None  # not in a repo: degrade, never run against the ambient CWD
        try:
            result = subprocess.run(
                ["git", "show", f"{ref}:{path}"],
                capture_output=True,
                text=True,
                timeout=_TIMEOUT,
                cwd=self._root,
            )
        except (
            FileNotFoundError,
            subprocess.TimeoutExpired,
            UnicodeDecodeError,
        ) as exc:
            # UnicodeDecodeError: git show returned non-UTF8 bytes that text=True
            # could not decode -- fail closed rather than crash the gate.
            msg = f"git show {ref}:{path} failed to run: {exc}"
            raise GitError(msg) from exc
        if result.returncode == 0:
            return result.stdout
        if self._is_absent_path(result.returncode, result.stderr):
            return None
        detail = result.stderr.strip() or f"exit {result.returncode}"
        msg = f"git show {ref}:{path} errored: {detail}"
        raise GitError(msg)

    @staticmethod
    def _is_absent_path(returncode: int, stderr: str) -> bool:
        """Return whether git's failure is a missing path at a valid ref.

        git reports that with exit 128 and a "does not exist in" /
        "exists on disk, but not in" message; any other failure (bad ref,
        corrupt repo) is not treated as benign absence.
        """
        if returncode != 128:
            return False
        lowered = stderr.lower()
        return "does not exist in" in lowered or "exists on disk, but not in" in lowered
