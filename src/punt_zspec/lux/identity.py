"""``ZSpecLuxIdentity`` — the per-session app identity and its menu labels.

z-spec is a lux *app*: it declares an explicit ``kind=app`` identity named for the
repo and pid rather than deriving a ``cli`` identity from the working directory.
Two same-repo sessions get distinct identities (the pid separates them), so each
owns its own menu entries and a click routes back to the session that registered
it. The name and the two menu labels carry both axes — tool (Tutorial vs Browse)
and session (repo + pid) — so a human with two sessions never clicks the wrong one.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Self, final

from punt_lux import ClientIdentity

__all__ = ["ZSpecLuxIdentity"]

_LEASE_TTL_SECONDS = 30.0


@final
class ZSpecLuxIdentity:
    """Build z-spec's app ``ClientIdentity`` and its two two-axis menu labels."""

    _repo: str
    _pid: int
    __slots__ = ("_pid", "_repo")

    def __new__(cls, repo: str, pid: int) -> Self:
        self = super().__new__(cls)
        self._repo = repo
        self._pid = pid
        return self

    @classmethod
    def for_session(cls) -> Self:
        """Resolve the identity from the git repo basename and this process pid."""
        return cls(cls._resolve_repo(Path.cwd()), os.getpid())

    @staticmethod
    def _resolve_repo(start: Path) -> str:
        """Return the enclosing git repo's basename, else the cwd basename."""
        for directory in (start, *start.parents):
            if (directory / ".git").exists():
                return directory.name
        return start.name or "z-spec"

    @property
    def app_name(self) -> str:
        """Return the luxd menu disambiguator: ``z-spec · <repo> · #<pid>``."""
        return f"z-spec · {self._repo} · #{self._pid}"

    @property
    def tutorial_label(self) -> str:
        """Return the Tutorial entry label carrying both the tool and session axes."""
        return f"z-spec Tutorial · {self._repo} · #{self._pid}"

    @property
    def browse_label(self) -> str:
        """Return the Browse entry label carrying both the tool and session axes."""
        return f"z-spec Browse · {self._repo} · #{self._pid}"

    @property
    def client_identity(self) -> ClientIdentity:
        """Return the app ``ClientIdentity`` (30s menu lease) both legs share."""
        return ClientIdentity(
            kind="app", name=self.app_name, lease_ttl=_LEASE_TTL_SECONDS
        )
