"""The per-process state an MCP server session bundles: root, gate, and lux."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Self, final

from punt_zspec.gate import EnablementGate
from punt_zspec.lux import ZSpecLuxSession
from punt_zspec.lux.project import ProjectRoot

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable

    from mcp.server.fastmcp import FastMCP

    from punt_zspec.commands.show import Display

__all__ = ["ServerContext"]


@final
class ServerContext:
    """One process's project root, enablement gate, and lux session.

    Bundles the state a set of bare module globals used to hold, plus the
    lifespan that operated on one of them from outside — state and its
    behavior live together, instead of globals and a free function reaching
    into one of them.

    One per MCP server process — ``__new__`` enforces it, rather than
    trusting the docstring: the duplicate-engine-instance failure vox paid
    for once, before ``voxd`` (architecture.md).
    """

    _constructed: ClassVar[bool] = False

    _project_root: Path
    _gate: EnablementGate
    _session: ZSpecLuxSession
    __slots__ = ("_gate", "_project_root", "_session")

    def __new__(cls) -> Self:
        if cls._constructed:
            msg = "ServerContext already constructed once in this process"
            raise RuntimeError(msg)
        cls._constructed = True
        self = super().__new__(cls)
        # Never ``Path.cwd()``: plugin.json's ``uv run --directory`` chdirs
        # before exec, so a plugin user's cwd is the z-spec checkout, not
        # their repo. Fixed for the process, so resolve once.
        self._project_root = ProjectRoot.resolve().path
        # §2.3: the marker is re-read on every call, so no state outlives an
        # ``enable`` run.
        self._gate = EnablementGate(self._project_root)
        # Lazily-connecting, so a down luxd never blocks import or the
        # check/test/animate surface; reads the same gate the tools do.
        self._session = ZSpecLuxSession(self._gate.is_open, cwd=self._project_root)
        return self

    @property
    def project_dir(self) -> str:
        """Return the project root as a string, the tools' directory default.

        What the directory-taking tools default to. A "." default meant the
        cwd, which is that same checkout: /z-spec:enable deposited the
        guide, wrote the marker, and edited CLAUDE.md inside z-spec's own
        repo and reported success while the user's repo went untouched.
        """
        return str(self._project_root)

    def guard[**P](self, tool: Callable[P, str]) -> Callable[P, str]:
        """Return *tool* wrapped so it declines wherever the marker is absent.

        Delegates to ``EnablementGate.guard`` — callers reach the behavior
        they use, not the gate object that owns it.
        """
        return self._gate.guard(tool)

    @property
    def display(self) -> Display:
        """Return the session's applet-identity display the tools render through."""
        return self._session.display

    async def sync(self) -> None:
        """Bring the receive leg into line with the repo's ``enabled`` marker.

        Delegates to ``ZSpecLuxSession.sync`` — also the enablement tool's
        way to refresh the menu right after an enable or disable.
        """
        await self._session.sync()

    @asynccontextmanager
    async def lifespan(self, _server: FastMCP) -> AsyncGenerator[None]:
        """Sync the menu listener to the marker on entry, drain it on shutdown.

        In a repo with no marker nothing connects, so z-spec contributes no
        entries to the shared lux menu. The plugin loads in every Claude Code
        session against one daemon serving one window; without this, every
        session would register its entries in every repo.
        """
        await self._session.sync()
        try:
            yield
        finally:
            await self._session.stop()
