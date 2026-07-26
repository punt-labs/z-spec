"""Git queries the suppression ratchet needs: base resolution and blob reads.

Git supplies the *base-commit* suppression baseline
(``git show <base>:.suppression-baseline.json``) so a PR cannot launder a rising
suppression count by hand-editing the in-tree baseline in the same change.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Self

_TIMEOUT = 10


class GitError(Exception):
    """A git command the ratchet depends on failed.

    Raised instead of degrading to a benign default, so the enforcement gate
    fails closed: a broken git call can never masquerade as "no change".
    """


class GitRepo:
    """Answer the ratchet's git questions, or degrade to ``None`` outside git."""

    _root: Path | None

    BASELINE_FILE: str = ".suppression-baseline.json"

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
                args, capture_output=True, text=True, timeout=_TIMEOUT, cwd=cwd
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

    def resolve_ref(self, ref: str) -> str | None:
        """Return the full commit hash for a ref, or ``None`` if unresolvable."""
        out = self._git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"])
        return out.strip() if out else None

    def merge_base(self, left: str, right: str) -> str | None:
        """Return the merge-base commit of two refs, or ``None``."""
        out = self._git(["merge-base", left, right])
        return out.strip() if out else None

    def resolve_base(self, base_ref: str | None) -> str | None:
        """Resolve the comparison base: explicit ref, else merge-base of main."""
        if base_ref is not None:
            return self.resolve_ref(base_ref)
        return self.merge_base("origin/main", "HEAD")

    def show_baseline(self, ref: str) -> dict[str, object] | None:
        """Return the suppression baseline committed at ``ref``, or ``None``.

        ``None`` means the blob genuinely does not exist at that ref — the
        first-adoption case. A real git error raises ``GitError`` rather than
        masquerading as absence, so the gate never fails open on a broken call.
        """
        out = self._show_file(ref, self.BASELINE_FILE)
        if out is None:
            return None
        blob = f"{ref}:{self.BASELINE_FILE}"
        try:
            loaded = json.loads(out)
        except json.JSONDecodeError as exc:
            msg = f"corrupt suppression baseline blob at {blob}: {exc}"
            raise GitError(msg) from exc
        if not isinstance(loaded, dict):
            msg = f"non-dict suppression baseline blob at {blob}"
            raise GitError(msg)
        parsed: dict[str, object] = loaded
        return parsed

    def _show_file(self, ref: str, path: str) -> str | None:
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
        if returncode != 128:
            return False
        lowered = stderr.lower()
        return "does not exist in" in lowered or "exists on disk, but not in" in lowered
