"""Transport ports for the z-spec receive leg: the listener and the menu client.

``HubListener`` is the one persistent WebSocket the subscription holds — its
``listen`` loop reconnects internally until ``stop``. ``MenuClient`` is the REST
surface that registers a menu callback under the session's app identity.
``ListenerFactory`` builds the listener from that same identity so a callback
registered over REST is delivered on the listener's stream. All three are
``Protocol``s (PY-TS-6) so the subscription is driven with fakes in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from punt_lux import CallbackHandler, EventHandler, OpError
    from punt_lux.hub_client import ConnectHandler
    from punt_lux.operations import Ok

__all__ = ["HubListener", "ListenerFactory", "MenuClient"]


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
    """The REST surface that registers a menu callback under the app identity."""

    def register_callback(self, callback_id: str, label: str) -> Ok | OpError:
        """Register a menu entry, returning success or a typed error."""
        ...


@runtime_checkable
class ListenerFactory(Protocol):
    """Build the persistent listener leg that shares the session's app identity."""

    def __call__(
        self,
        *,
        on_callback: CallbackHandler,
        on_event: EventHandler,
        on_connect: ConnectHandler,
    ) -> HubListener:
        """Return a listener wired to re-register callbacks on every handshake."""
        ...
