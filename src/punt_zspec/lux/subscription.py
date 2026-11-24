"""``ZSpecSubscription`` — z-spec's receive leg: one hub connection, menu, dispatch.

The subscription holds one live listener at a time. Its ``on_connect`` (fired
after every handshake — first connect and every internal reconnect) re-registers
both menu entries, so a luxd outage that lapses the lease heals the instant the
listener rejoins (register-fresh). A click arrives as ``on_callback`` and is
handed to the click runner, which owns everything the click then does.

Both of those consult ``is_enabled`` first. The repo's ``enabled`` marker is the
menu's authority exactly as it is the tool surface's, and it is re-read at each
of them rather than read once, because the marker outlives neither the process
nor the connection: a ``disable`` (or a branch checkout) between two handshakes
must leave the shared window with no z-spec entries and no live click.

An outage is logged once, not once per retry: its first failure warns, repeats
go to DEBUG, and its end is one INFO summary — recovered at the next handshake,
or terminated when the leg stops first.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Self, final

from punt_lux import HubUnavailableError

from punt_zspec.lux.outage import ZSpecLegOutage

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from punt_zspec.lux.click import ZSpecClickRunner
    from punt_zspec.lux.command_ports import MenuRegistrar
    from punt_zspec.lux.entry import ZSpecMenuEntry
    from punt_zspec.lux.ports import HubListener, ListenerFactory

__all__ = ["ZSpecSubscription"]

logger = logging.getLogger(__name__)

_RETRY_SECONDS = 5.0


@final
class ZSpecSubscription:
    """Own z-spec's one hub connection, its two menu entries, and click routing."""

    _entries: tuple[ZSpecMenuEntry, ...]
    _menu: MenuRegistrar
    _listen: ListenerFactory
    _click: ZSpecClickRunner
    _is_enabled: Callable[[], bool]
    _listener: HubListener | None
    _stopped: bool
    _outage: ZSpecLegOutage
    __slots__ = (
        "_click",
        "_entries",
        "_is_enabled",
        "_listen",
        "_listener",
        "_menu",
        "_outage",
        "_stopped",
    )

    def __new__(
        cls,
        entries: tuple[ZSpecMenuEntry, ...],
        menu: MenuRegistrar,
        listen: ListenerFactory,
        click: ZSpecClickRunner,
        is_enabled: Callable[[], bool],
    ) -> Self:
        """Assemble the subscription from its collaborators.

        Args:
            entries: The menu entries to register.
            menu: Registers each entry's callback with the Hub.
            listen: Opens the listener connection that delivers clicks.
            click: Runs the entry a click names.
            is_enabled: Reports whether the repository's ``enabled`` marker is present.
        """
        self = super().__new__(cls)
        self._entries = entries
        self._menu = menu
        self._listen = listen
        self._click = click
        self._is_enabled = is_enabled
        self._listener = None  # None until first connect / after stop
        self._stopped = False
        self._outage = ZSpecLegOutage()
        return self

    async def run(self) -> None:
        """Hold the receive leg open, retrying a down luxd; return on stop.

        Entering re-arms the leg: ``stop()`` leaves ``_stopped`` set and the
        session reuses this subscription across a stop/start cycle, so without
        clearing it here the second run would exit before its first connect and
        the menu would silently never register again.

        A down luxd is retried so the menu appears the moment luxd starts; any
        other fault is logged and retried, so the leg never dies silently. A
        listener that returns normally without a stop request (a
        reconnect-exhausted punt_lux that returns rather than raises) is
        reconnected too, never a silent death. Each outage logs once when it
        opens and once when it ends (see ``ZSpecLegOutage``). Cancellation on
        shutdown propagates cleanly out.
        """
        self._stopped = False
        self._listener = None  # the previous run's listener is closed and stale
        try:
            await self._retry_until_stopped()
        finally:
            self._outage.close("terminated")

    async def _retry_until_stopped(self) -> None:
        """Connect and listen, backing off after each failure, until stopped."""
        # ``_stopped`` flips via ``stop()`` from another thread mid-``listen``; a
        # method guard keeps mypy from narrowing it to a constant across the await.
        while not self._is_stopped():
            try:
                await self._connect_and_listen()
            except HubUnavailableError:
                self._outage.failed("luxd is down", _RETRY_SECONDS)
            except Exception:
                self._outage.failed("the menu leg failed", _RETRY_SECONDS, fault=True)
            else:
                if self._is_stopped():
                    return
                self._outage.failed("the listener returned unstopped", _RETRY_SECONDS)
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
        """Re-register both menu entries after every handshake, where z-spec is on.

        The marker decides per handshake. A repo turned off while the server ran
        must not have its entries put back on the shared window by the next
        reconnect, and one turned on gets them at the connect that follows.
        A handshake also ends any outage the leg was retrying through.
        """
        self._outage.close("recovered")
        if not self._is_enabled():
            logger.info("z-spec is not enabled here — registering no menu entries")
            return
        for entry in self._entries:
            await self._menu.register(entry.callback_id, entry.title, entry.scene_id)

    async def on_event(self, topic: str, payload: Mapping[str, object]) -> None:
        """Ignore topic events: z-spec's scenes publish none; clicks are callbacks."""
        logger.debug("ignoring Lux topic event: reason=no_topic_subscriptions")

    async def on_callback(self, callback_id: str) -> None:
        """Route a menu click to its entry and hand it to the click runner.

        The marker is re-read per click rather than trusted from registration
        time. An entry the shared window still shows after a ``disable`` — the
        lux lease outlives the marker — must dispatch nothing at all.
        """
        if (entry := self._entry_for(callback_id)) is None:
            logger.debug("ignoring Lux callback: reason=unknown_menu_entry")
            return
        if not self._is_enabled():
            logger.info("ignoring Lux callback: reason=z_spec_disabled")
            return
        await self._click.run(entry)

    def _entry_for(self, callback_id: str) -> ZSpecMenuEntry | None:
        """Return the entry a click selects, or ``None`` if it is not z-spec's.

        ``None`` is the documented "not ours": one hub delivers every app's
        callbacks on the one stream, so an id z-spec never registered is
        routine traffic rather than a fault.
        """
        return next((e for e in self._entries if e.matches(callback_id)), None)

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
