"""``ZSpecLuxIdentity`` — the per-session app identity and its menu labels.

z-spec is a lux *app*: an explicit ``kind=app`` identity named for the repo and pid.
The pid separates same-repo sessions; the two menu labels carry tool and session axes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Self, final

from punt_lux import ClientIdentity

from punt_zspec.lux.project import ProjectRoot

__all__ = ["ZSpecLuxIdentity"]

_LEASE_TTL_SECONDS = 30.0


@final
class ZSpecLuxIdentity:
    """Build z-spec's app ``ClientIdentity`` and its two two-axis menu labels."""

    _repo: str
    _pid: int
    _client_identity: ClientIdentity
    __slots__ = ("_client_identity", "_pid", "_repo")

    def __new__(cls, repo: str, pid: int) -> Self:
        self = super().__new__(cls)
        self._repo = repo
        self._pid = pid
        # Build the identity once so both legs hand luxd the SAME object — luxd
        # links a REST registration to the listen leg only when byte-identical.
        self._client_identity = ClientIdentity(
            kind="app", name=self.app_name, lease_ttl=_LEASE_TTL_SECONDS
        )
        return self

    @classmethod
    def for_session(cls) -> Self:
        """Resolve the identity from the git repo basename and this process pid.

        The repo walk starts from the user's project root, not ``Path.cwd()``:
        the plugin-launched server's cwd is the plugin checkout (pinned by
        ``--directory``), so cwd would name z-spec's own repo for every session.
        """
        return cls(cls._resolve_repo(ProjectRoot.resolve().path), os.getpid())

    @staticmethod
    def _resolve_repo(start: Path) -> str:
        """Return the enclosing git repo's basename, else the cwd basename."""
        for directory in (start, *start.parents):
            if (directory / ".git").exists():
                return directory.name
        return start.name or "z-spec"

    @property
    def app_name(self) -> str:
        """Return the identity name ``z-spec / <repo> / #<pid>`` — ASCII-only.

        It rides the ``X-Lux-Client-Name`` header luxd hashes into the ConnectionId.
        A non-ASCII separator (e.g. ``·``, U+00B7) encodes to different bytes on the
        WebSocket and REST legs, so luxd links no listen leg and refuses the register.
        """
        return f"z-spec / {self._repo} / #{self._pid}"

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
        """Return the one app ``ClientIdentity`` (30s lease) both legs share."""
        return self._client_identity
