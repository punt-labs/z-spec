"""The per-process state an MCP server session bundles: root, gate, and lux."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Self, final

from punt_zspec.gate import EnablementGate
from punt_zspec.lux import ZSpecLuxSession
from punt_zspec.lux.project import ProjectRoot

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from mcp.server.fastmcp import FastMCP

__all__ = ["ServerContext"]


@final
class ServerContext:
    """One process's project root, enablement gate, and lux session.

    Bundles the state a set of bare module globals used to hold, plus the
    lifespan that operated on one of them from outside — state and its
    behavior live together, instead of globals and a free function reaching
    into one of them.
    """

    _project_root: Path
    _gate: EnablementGate
    _session: ZSpecLuxSession
    __slots__ = ("_gate", "_project_root", "_session")

    def __new__(cls) -> Self:
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
        """Return the project root as a string, the tools' directory default."""
        return str(self._project_root)

    @property
    def gate(self) -> EnablementGate:
        return self._gate

    @property
    def session(self) -> ZSpecLuxSession:
        return self._session

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
