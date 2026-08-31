"""``ZSpecLuxIdentity`` — the applet identity one z-spec MCP server declares.

z-spec is a lux *applet*: one client per server process, declaring the user's
open project as the repository it works in. luxd names that client's Clients-menu
submenu after the repository (``ClientIdentity.menu_label`` returns the repo
basename, never the declared name), so the repo is what reads and the name is a
distinctness token feeding the connection id luxd hashes.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Self, final

from punt_lux import ClientIdentity
from punt_lux.domain.hub import applet_name_format

from punt_zspec.lux.project import ProjectRoot

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ZSpecLuxIdentity"]

_PROGRAM = "z-spec"


@final
class ZSpecLuxIdentity:
    """Declare the one applet ``ClientIdentity`` both of z-spec's legs hand luxd."""

    _client_identity: ClientIdentity
    __slots__ = ("_client_identity",)

    def __new__(cls, project: Path) -> Self:
        # luxd's ClientIdentity validator rejects any applet name that is not the
        # four-part shape ``lux · <repo> · #<pid> · <program>`` (DES-067). Delegate
        # to the punt-lux helper so writer and reader move together; the pid is
        # the Claude session's — this server's parent — because luxd groups
        # Clients-menu entries by the session pid it parses from the name, and
        # every applet of one session (vox-panel included) must stamp the same
        # one to share a submenu. Two sessions still keep distinct connections:
        # each has its own session pid.
        self = super().__new__(cls)
        self._client_identity = ClientIdentity(
            kind="applet",
            name=applet_name_format.format_name(
                repo_name=project.name,
                session_pid=os.getppid(),
                program=_PROGRAM,
            ),
            repo=str(project),
        )
        return self

    @classmethod
    def for_session(cls) -> Self:
        """Declare this process's identity over the user's open project.

        Uses :class:`ProjectRoot` rather than ``Path.cwd()``: the plugin-launched
        server's cwd is the plugin checkout (pinned by ``--directory``), so cwd
        would label every session's submenu with z-spec's own repo.
        """
        return cls(ProjectRoot.resolve().path)

    @property
    def client_identity(self) -> ClientIdentity:
        """Return the applet identity luxd knows this server process by."""
        return self._client_identity
