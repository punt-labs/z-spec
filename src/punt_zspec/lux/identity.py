"""``ZSpecLuxIdentity`` — the applet identity one z-spec MCP server declares.

z-spec is a lux *applet*: one client per server process, declaring the user's open
project as the repository it works in. luxd names that client's Clients-menu
submenu after the repository (``ClientIdentity.menu_label`` returns the repo's
basename, never the declared name), and numbers two clients that read the same
way. So the repo is what reads, and the name is a distinctness token: it feeds
the connection id luxd hashes, and nothing a user sees.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Self, final

from punt_lux import ClientIdentity

from punt_zspec.lux.project import ProjectRoot

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ["ZSpecLuxIdentity"]

_TOOL_NAME = "z-spec"

# How long luxd may go without hearing from this server before it sweeps the
# session and its menu entries. The applet convention: the listen leg renews
# every 15s, so four beats may be lost — long enough to ride out a luxd restart,
# short enough that a killed session's entries do not linger on a shared window.
_LEASE_TTL_SECONDS = 60.0


@final
class ZSpecLuxIdentity:
    """Declare the one applet ``ClientIdentity`` both of z-spec's legs hand luxd."""

    _client_identity: ClientIdentity
    __slots__ = ("_client_identity",)

    def __new__(cls, project: Path) -> Self:
        self = super().__new__(cls)
        # Built once so both legs hand luxd the SAME identity: luxd derives a
        # connection from (kind, name, repo, agent) and links a REST menu
        # registration to the listen leg only when the two derive alike.
        #
        # The name is a distinctness token, not a label — the menu reads the repo
        # basename and never the name. The pid is what it carries, because without
        # it two sessions on one repository derive one connection and the second
        # takes the listener slot, clearing the callbacks the first registered:
        # clicks that do nothing, with no error anywhere to find. It is this
        # process's own pid, never a caller's argument — a declared pid naming some
        # other process would be a token that lies. Decimal rather than luxd's hex
        # so a person reading it in `Details` can `ps -p` it straight off.
        self._client_identity = ClientIdentity(
            kind="applet",
            name=f"{_TOOL_NAME} #{os.getpid()}",
            repo=str(project),
            lease_ttl=_LEASE_TTL_SECONDS,
        )
        return self

    @classmethod
    def for_session(cls) -> Self:
        """Declare this process's identity over the user's open project.

        The project comes from ``ProjectRoot``, never ``Path.cwd()``: the
        plugin-launched server's cwd is the plugin checkout (pinned by
        ``--directory``), so cwd would declare z-spec's own repository for every
        session and every menu would read "z-spec". ``ProjectRoot`` yields an
        absolute path either way, which is what ``ClientIdentity`` requires of a
        declared repository.
        """
        return cls(ProjectRoot.resolve().path)

    @property
    def client_identity(self) -> ClientIdentity:
        """Return the applet identity luxd knows this server process by."""
        return self._client_identity
