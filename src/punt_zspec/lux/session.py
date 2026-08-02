"""``ZSpecLuxSession`` — the per-process lux menu session the FastMCP lifespan owns.

One session per MCP server process (one per Claude Code session). It owns the app
identity, the server-owned ``Display`` every render path shares, and the listener
task. :meth:`start` spawns the receive leg in the lifespan; :meth:`stop` cancels
and drains it. A down luxd at startup is non-fatal — the listener retries and the
check/test/animate tools keep working — because the render path and the listener
only ever touch luxd lazily.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Self, final

from punt_zspec.display import LuxDisplay
from punt_zspec.lux.clients import ZSpecLuxClients
from punt_zspec.lux.menu import ZSpecMenuRegistrar
from punt_zspec.lux.project import ProjectRoot
from punt_zspec.lux.subscription import (
    ZSpecClickCommands,
    ZSpecMenuEntry,
    ZSpecSubscription,
)

if TYPE_CHECKING:
    from punt_zspec.commands.show import Display

__all__ = ["ZSpecLuxSession"]

logger = logging.getLogger(__name__)

_TUTORIAL_CALLBACK = "z-spec-tutorial"
_BROWSE_CALLBACK = "z-spec-browse"


@final
class ZSpecLuxSession:
    """Own the app-identity clients, the shared display, and the listener task."""

    _clients: ZSpecLuxClients
    _display: LuxDisplay
    _subscription: ZSpecSubscription
    _task: asyncio.Task[None] | None
    __slots__ = ("_clients", "_display", "_subscription", "_task")

    def __new__(
        cls,
        clients: ZSpecLuxClients | None = None,
        cwd: Path | None = None,
        tutorial_manifest: Path | None = None,
    ) -> Self:
        # None defaults (PY-TS-14): the real per-session app identity, the user's
        # project root, and the shipped manifest; tests inject fixed ones. The
        # Browse target is the project root, not ``Path.cwd()``: the plugin-launched
        # server's cwd is the plugin checkout (pinned by ``--directory``), so cwd
        # would browse z-spec's own specs instead of the user's.
        lux = clients if clients is not None else ZSpecLuxClients()
        directory = cwd if cwd is not None else ProjectRoot.resolve().path
        manifest = (
            tutorial_manifest
            if tutorial_manifest is not None
            else cls._default_tutorial_manifest()
        )
        identity = lux.identity
        self = super().__new__(cls)
        self._clients = lux
        # Every render path shares this app-identity display, so pushes and the
        # listen stream resolve to one session — the callback-delivery precondition.
        self._display = LuxDisplay(connect=lux.rest)
        entries = (
            ZSpecMenuEntry(
                callback_id=_TUTORIAL_CALLBACK,
                label=identity.tutorial_label,
                scene_id="z-spec-tutorial",
                scene_title="Z-Spec Tutorial",
                factory=ZSpecClickCommands.tutorial,
                target=manifest,
            ),
            ZSpecMenuEntry(
                callback_id=_BROWSE_CALLBACK,
                label=identity.browse_label,
                scene_id="z-spec-picker",
                scene_title="Z Specs",
                factory=ZSpecClickCommands.picker,
                target=directory,
            ),
        )
        self._subscription = ZSpecSubscription(
            entries=entries,
            menu=ZSpecMenuRegistrar(lux.rest),
            listen=lux.listen,
            display=self._display,
        )
        self._task = None
        return self

    @property
    def display(self) -> Display:
        """Return the server-owned app-identity display the tools render through."""
        return self._display

    async def start(self) -> None:
        """Spawn the listener task on the MCP server's event loop (best-effort).

        Idempotent while the leg is *live*: a second ``start()`` would orphan
        the running task (``stop()`` only cancels the most recent), so a live
        task short-circuits the spawn. A *finished* task is not that case — it
        is a dead receive leg, and refusing there would leave the menu down for
        the life of the process, so a finished task is replaced.
        """
        task = self._task
        if task is not None and not task.done():
            logger.warning("z-spec listener already started; ignoring re-start")
            return
        if task is not None:
            self._report_exit(task)
        self._task = asyncio.create_task(self._subscription.run())

    async def stop(self) -> None:
        """Stop the receive leg and drain the task cleanly on shutdown."""
        self._subscription.stop()
        task = self._task
        self._task = None
        if task is None:
            return
        if task.done():
            # Nothing left to cancel, but the exception of a leg that died on
            # its own is still ours to consume: awaiting it here would raise it
            # out of the lifespan's shutdown instead.
            self._report_exit(task)
            return
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    @staticmethod
    def _report_exit(task: asyncio.Task[None]) -> None:
        """Log why a finished listener task ended, consuming its exception.

        ``run()`` guards its own loop, so an exception here escaped that guard
        and would otherwise surface only as asyncio's "exception was never
        retrieved" at garbage-collection time, detached from the restart.
        """
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            logger.warning("z-spec listener had died (%r); starting a new one", exc)

    @staticmethod
    def _default_tutorial_manifest() -> Path:
        """Return the shipped ``tutorials/intro/manifest.toml``.

        The installed plugin runs the MCP server from site-packages, where the
        source tree's ``parents[3]`` holds no ``tutorials/``. plugin.json injects
        ``ZSPEC_PLUGIN_ROOT`` (= ``CLAUDE_PLUGIN_ROOT``, the plugin checkout that
        ships the tutorials) into the server env; prefer it. Fall back to the
        src-layout resolution for a dev checkout where the env var is unset. An
        absent manifest under either root is tolerated at click time — the
        Tutorial command reports ``spec_not_found`` and renders an error scene.
        """
        root = os.environ.get("ZSPEC_PLUGIN_ROOT")
        base = Path(root) if root else Path(__file__).resolve().parents[3]
        return base / "tutorials" / "intro" / "manifest.toml"
