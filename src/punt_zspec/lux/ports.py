"""Transport ports for the z-spec receive leg: the listener and the menu surface.

``HubListener`` is the one persistent WebSocket the subscription holds — its
``listen`` loop reconnects internally until ``stop``. ``MenuClient`` is the one
REST surface the leg drives under the session's applet identity: registering a
menu callback. The frame-raise leg is gone — a client may read the display but
never mutate it (punt-lux DES-088), so ``register_callback`` now carries the
entry's scene as ``frame_id`` and luxd raises that frame Display-locally on
click. ``ListenerFactory`` builds the listener from that same identity so a
callback registered over REST is delivered on the listener's stream. All are
``Protocol``s (PY-TS-6) so the receive leg is driven with fakes in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from punt_lux import CallbackHandler, EventHandler, OpError
    from punt_lux.hub_client import ConnectHandler
    from punt_lux.operations import Ok

__all__ = [
    "HubListener",
    "ListenerFactory",
    "LuxRestClient",
    "MenuClient",
]


@runtime_checkable
class HubListener(Protocol):
    """The one live hub connection: subscribe, then listen with reconnect."""

    def subscribe(self, *topics: str) -> None:
        """Record topics to (re)subscribe on every connect; call before listen."""
        ...

    async def listen(self) -> None:
        """Hold the connection open, dispatching frames, until :meth:`stop`."""
        ...

    def stop(self) -> None:
        """Ask the listen loop to finish after its current connection closes."""
        ...


@runtime_checkable
class MenuClient(Protocol):
    """The REST surface that registers a menu callback under the applet identity."""

    def register_callback(
        self, callback_id: str, label: str, frame_id: str
    ) -> Ok | OpError:
        """Register a menu entry — luxd raises ``frame_id`` on click (DES-088)."""
        ...


@runtime_checkable
class LuxRestClient(MenuClient, Protocol):
    """The subset of ``LuxClient.sync`` z-spec consumes over REST.

    Aliased to :class:`MenuClient`, the only REST capability z-spec drives now
    the frame-raise leg is gone, and kept here so the receive leg never types
    against ``punt_lux.client._sync_ops`` — a private punt-lux module path.
    """


@runtime_checkable
class ListenerFactory(Protocol):
    """Build the persistent listener leg that shares the session's applet identity."""

    def __call__(
        self,
        *,
        on_callback: CallbackHandler,
        on_event: EventHandler,
        on_connect: ConnectHandler,
    ) -> HubListener:
        """Return a listener wired to re-register callbacks on every handshake."""
        ...
