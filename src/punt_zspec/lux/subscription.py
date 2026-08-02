"""``ZSpecSubscription`` — z-spec's receive leg: one hub connection, menu, dispatch.

The subscription holds one live listener at a time. Its ``on_connect`` (fired
after every handshake — first connect and every internal reconnect) re-registers
both menu entries, so a >30s luxd outage that lapses the lease heals the instant
the listener rejoins (register-fresh). A click arrives as ``on_callback`` and
routes to the same command a menu tool would run — no duplicated render logic.

Nothing renders inline on the FastMCP event loop: the placeholder raise and the
full ``command.run`` both go through :func:`asyncio.to_thread`, so a blocking REST
round-trip never starves the loop that serves check/test/animate (ADR §5.3).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Self, final

from punt_lux import HubUnavailableError
from punt_lux.protocol import TextElement

from punt_zspec.browser import build_browser_scene, build_spec_picker
from punt_zspec.commands.browse import BrowseCommand
from punt_zspec.commands.picker import PickerCommand
from punt_zspec.commands.show import Display, DisplayError

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from punt_zspec.commands.result import CommandError
    from punt_zspec.lux.command_ports import (
        ClickCommand,
        ClickCommandFactory,
        ClickOutcome,
        MenuRegistrar,
    )
    from punt_zspec.lux.ports import HubListener, ListenerFactory

__all__ = ["ZSpecClickCommands", "ZSpecMenuEntry", "ZSpecSubscription"]

logger = logging.getLogger(__name__)

_RETRY_SECONDS = 5.0


@final
class ZSpecClickCommands:
    """Bind the two menu click-commands to the server-owned ``Display``.

    Each factory is one more caller of a shipped command — the Tutorial entry runs
    ``BrowseCommand`` on the shipped manifest, the Browse entry runs
    ``PickerCommand`` on the cwd — so the menu holds no render logic of its own.
    """

    __slots__ = ()

    @staticmethod
    def tutorial(display: Display) -> ClickCommand:
        """Build the Tutorial command: the browser over the shipped manifest."""
        return BrowseCommand(build=build_browser_scene, display=display)

    @staticmethod
    def picker(display: Display) -> ClickCommand:
        """Build the Browse command: the picker over the working directory."""
        return PickerCommand(build=build_spec_picker, display=display)


@final
@dataclass(frozen=True, slots=True)
class ZSpecMenuEntry:
    """One menu entry: its callback id, two-axis label, scene, and command.

    ``scene_id`` is both the id the click raises and the ``frame_id`` its command
    renders into — one Hub scene, so the placeholder is replaced rather than
    stranded (ADR §5.2). ``target`` is the command's argument (manifest or cwd).
    """

    callback_id: str
    label: str
    scene_id: str
    scene_title: str
    factory: ClickCommandFactory
    target: Path

    def matches(self, callback_id: str) -> bool:
        """Return whether a click's ``callback_id`` selects this entry."""
        return self.callback_id == callback_id

    def run(self, display: Display) -> ClickOutcome:
        """Run this entry's command on ``display`` and return its outcome.

        Blocking — call off-thread. The command captures a down display as a
        typed failure rather than raising; the caller reads the returned outcome
        to heal a placeholder a failed render would otherwise strand.
        """
        return self.factory(display).run(self.target, frame_id=self.scene_id)

    def placeholder(self) -> TextElement:
        """Return the minimal loading scene raised before the full render."""
        return TextElement(
            id=f"{self.scene_id}-loading", content=f"Loading {self.scene_title}…"
        )

    def error_scene(self, error: CommandError) -> TextElement:
        """Return the scene that replaces the placeholder when the render fails."""
        return TextElement(
            id=f"{self.scene_id}-error",
            content=f"{self.scene_title} failed: {error.message}",
        )


@final
class ZSpecSubscription:
    """Own z-spec's one hub connection, its two menu entries, and click dispatch."""

    _entries: tuple[ZSpecMenuEntry, ...]
    _menu: MenuRegistrar
    _listen: ListenerFactory
    _display: Display
    _listener: HubListener | None
    _stopped: bool
    __slots__ = ("_display", "_entries", "_listen", "_listener", "_menu", "_stopped")

    def __new__(
        cls,
        entries: tuple[ZSpecMenuEntry, ...],
        menu: MenuRegistrar,
        listen: ListenerFactory,
        display: Display,
    ) -> Self:
        self = super().__new__(cls)
        self._entries = entries
        self._menu = menu
        self._listen = listen
        self._display = display
        self._listener = None  # None until first connect / after stop
        self._stopped = False
        return self

    async def run(self) -> None:
        """Hold the receive leg open, retrying a down luxd; return on stop.

        Entering re-arms the leg: ``stop()`` leaves ``_stopped`` set and the
        session reuses this subscription across a stop/start cycle, so without
        clearing it here the second run would exit before its first connect and
        the menu would silently never register again.

        A down luxd is retried with a warning so the menu appears the moment luxd
        starts; any other fault is logged and retried, so the leg never dies
        silently. A listener that returns normally without a stop request (a
        reconnect-exhausted punt_lux that returns rather than raises) is logged
        and reconnected too, never a silent death. Cancellation on shutdown
        propagates cleanly out.
        """
        self._stopped = False
        self._listener = None  # the previous run's listener is closed and stale
        attempt = 0
        # ``_stopped`` flips via ``stop()`` from another thread mid-``listen``; a
        # method guard keeps mypy from narrowing it to a constant across the await.
        while not self._is_stopped():
            attempt += 1
            try:
                await self._connect_and_listen()
            except HubUnavailableError:
                logger.warning(
                    "luxd down; retrying z-spec menu leg in %.1fs (attempt %d)",
                    _RETRY_SECONDS,
                    attempt,
                )
                await asyncio.sleep(_RETRY_SECONDS)
            except Exception:
                logger.exception(
                    "[lux] z-spec menu leg failed; restarting in %.1fs (attempt %d)",
                    _RETRY_SECONDS,
                    attempt,
                )
                await asyncio.sleep(_RETRY_SECONDS)
            else:
                if self._is_stopped():
                    return
                logger.warning(
                    "[lux] z-spec listener returned without stop; "
                    "reconnecting in %.1fs (attempt %d)",
                    _RETRY_SECONDS,
                    attempt,
                )
                await asyncio.sleep(_RETRY_SECONDS)

    async def _connect_and_listen(self) -> None:
        """Build one fresh listener off-thread and listen until stopped.

        Menu registration rides ``on_connect`` (fired on every handshake), not
        this loop, so an internal reconnect re-registers register-fresh.
        """
        listener = await asyncio.to_thread(
            self._listen,
            on_callback=self.on_callback,
            on_event=self.on_event,
            on_connect=self.on_connect,
        )
        self._listener = listener
        await listener.listen()

    async def on_connect(self) -> None:
        """Re-register both menu entries after every handshake (register-fresh)."""
        for entry in self._entries:
            await self._menu.register(entry.callback_id, entry.label)

    async def on_event(self, topic: str, payload: Mapping[str, object]) -> None:
        """Ignore topic events: z-spec's scenes publish none; clicks are callbacks."""
        logger.debug("ignoring unexpected z-spec event on %s: %r", topic, dict(payload))

    async def on_callback(self, callback_id: str) -> None:
        """Route a menu click to its entry: raise instantly, then render off-loop."""
        for entry in self._entries:
            if entry.matches(callback_id):
                await self._dispatch(entry)
                return
        logger.debug("no z-spec menu entry for callback %r", callback_id)

    async def _dispatch(self, entry: ZSpecMenuEntry) -> None:
        """Raise the placeholder, render off-loop, and heal a stranded scene.

        A failed render (empty cwd, unreadable spec, down luxd) returns a typed
        failure rather than raising; without inspecting it the placeholder reads
        "Loading…" forever. On failure the error is logged and the placeholder
        is replaced with the failure text so the user sees why (ADR §5.2).
        """
        await self._raise_scene(entry)
        outcome = await asyncio.to_thread(entry.run, self._display)
        error = outcome.error
        if error is not None:
            logger.warning(
                "[lux] %s click failed: %s", entry.callback_id, error.message
            )
            await self._render_error(entry, error)

    async def _render_error(self, entry: ZSpecMenuEntry, error: CommandError) -> None:
        """Replace the stranded placeholder with the failure text (off-thread)."""
        try:
            await asyncio.to_thread(
                self._display.show,
                entry.error_scene(error),
                frame_id=entry.scene_id,
                frame_title=entry.scene_title,
            )
        except DisplayError as exc:
            logger.warning("could not render error scene %s: %s", entry.scene_id, exc)

    async def _raise_scene(self, entry: ZSpecMenuEntry) -> None:
        """Push a minimal placeholder under ``scene_id`` for an instant response.

        The raise behavior lives only here, so a future single-call Hub raise (a
        next-release punt_lux API, absent at the ``>=0.22.1,<0.23`` pin) is a
        one-line swap. At this pin every click does the placeholder-then-full
        sequence (ADR §2.4); the push is a blocking render, so it runs off-thread.
        """
        try:
            await asyncio.to_thread(
                self._display.show,
                entry.placeholder(),
                frame_id=entry.scene_id,
                frame_title=entry.scene_title,
            )
        except DisplayError as exc:
            logger.warning("could not raise placeholder %s: %s", entry.scene_id, exc)

    def _is_stopped(self) -> bool:
        """Whether ``stop()`` was requested.

        A method, not a bare ``self._stopped`` read, so the run-loop guard does
        not let the type checker narrow ``_stopped`` to a constant across the
        ``listen`` await that another thread's ``stop()`` can flip.
        """
        return self._stopped

    def stop(self) -> None:
        """Ask the receive leg to finish after its current connection closes."""
        self._stopped = True
        listener = self._listener
        if listener is not None:
            listener.stop()
