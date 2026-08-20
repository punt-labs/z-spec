"""``ZSpecLuxSession`` — the per-process lux menu session the FastMCP lifespan owns.

One session per MCP server process (one per Claude Code session). It owns the
applet identity, the server-owned ``Display`` every render path shares, and the
listener task. :meth:`sync` is the one both callers use — the lifespan at startup
and the enablement tool after every run — and it reads the repo's ``enabled``
marker to decide between :meth:`start` and :meth:`stop`. A down luxd at startup is
non-fatal — the listener retries and the check/test/animate tools keep working —
because the render path and the listener only ever touch luxd lazily.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Self, final

from punt_zspec.display import LuxDisplay
from punt_zspec.lux.click import ZSpecClickRunner, ZSpecFrameRaiser
from punt_zspec.lux.clients import ZSpecLuxClients
from punt_zspec.lux.entry import ZSpecMenuEntries
from punt_zspec.lux.menu import ZSpecMenuRegistrar
from punt_zspec.lux.project import ProjectRoot
from punt_zspec.lux.subscription import ZSpecSubscription

if TYPE_CHECKING:
    from collections.abc import Callable

    from punt_zspec.commands.show import Display

__all__ = ["ZSpecLuxSession"]

logger = logging.getLogger(__name__)


@final
class ZSpecLuxSession:
    """Own the shared applet-identity display, the receive leg, and its task."""

    _display: LuxDisplay
    _is_enabled: Callable[[], bool]
    _subscription: ZSpecSubscription
    _task: asyncio.Task[None] | None
    __slots__ = ("_display", "_is_enabled", "_subscription", "_task")

    def __new__(
        cls,
        is_enabled: Callable[[], bool],
        clients: ZSpecLuxClients | None = None,
        cwd: Path | None = None,
        tutorial_manifest: Path | None = None,
    ) -> Self:
        # None defaults (PY-TS-14): the real per-session applet identity, the user's
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
        self = super().__new__(cls)
        # Every render path shares this applet-identity display, so pushes and the
        # listen stream resolve to one session — the callback-delivery precondition.
        self._display = LuxDisplay(connect=lux.rest)
        self._is_enabled = is_enabled
        self._subscription = ZSpecSubscription(
            entries=ZSpecMenuEntries.of(
                tutorial_manifest=manifest, browse_root=directory
            ),
            menu=ZSpecMenuRegistrar(lux.rest),
            listen=lux.listen,
            click=ZSpecClickRunner(self._display, ZSpecFrameRaiser(lux.rest)),
            is_enabled=is_enabled,
        )
        self._task = None
        return self

    @property
    def display(self) -> Display:
        """Return the server-owned applet-identity display the tools render through."""
        return self._display

    async def sync(self) -> None:
        """Bring the receive leg into line with the repo's ``enabled`` marker.

        The one call the lifespan and the enablement tool share, and what makes
        the menu as immediate as the gated tools already are: ``enable`` in a
        previously unmarked repo brings the listener up — and with it the
        Tutorial and Browse entries — without waiting for a reconnect, and
        ``disable`` drops the connection, so the lease lapses and the entries
        leave the shared window. Idempotent in both directions.
        """
        if self._is_enabled():
            await self.start()
            return
        logger.info("z-spec is not enabled here — the lux menu stays off")
        await self.stop()

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
            logger.warning("the z-spec listener died: %r", exc)

    @staticmethod
    def _default_tutorial_manifest() -> Path:
        """Return the shipped ``tutorials/intro/manifest.toml``.

        The installed plugin runs the MCP server from site-packages, where the
        source tree holds no tutorials at all. plugin.json injects
        ``ZSPEC_PLUGIN_ROOT`` (= ``CLAUDE_PLUGIN_ROOT``, the plugin checkout that
        ships the tutorials) into the server env; prefer it, and the tutorials sit
        directly under it because the whole shippable surface — manifest, commands,
        hooks, tutorials — lives in one ``plugin/`` directory. Fall back to that
        same directory inside a dev checkout (``parents[3]`` is the repo root) when
        the env var is unset. An absent manifest under either root is tolerated at
        click time — the Tutorial command reports ``spec_not_found`` and renders an
        error scene.
        """
        root = os.environ.get("ZSPEC_PLUGIN_ROOT")
        base = Path(root) if root else Path(__file__).resolve().parents[3] / "plugin"
        return base / "tutorials" / "intro" / "manifest.toml"
