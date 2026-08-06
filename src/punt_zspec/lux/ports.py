"""Transport ports for the z-spec receive leg: the listener and the REST surfaces.

``HubListener`` is the one persistent WebSocket the subscription holds — its
``listen`` loop reconnects internally until ``stop``. ``MenuClient`` and
``FrameRaiseClient`` are the two REST surfaces the leg drives under the session's
applet identity: registering a menu callback, and bringing a clicked entry's frame
to the front. ``ListenerFactory`` builds the listener from that same identity so a
callback registered over REST is delivered on the listener's stream. All are
``Protocol``s (PY-TS-6) so the receive leg is driven with fakes in tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from punt_lux import CallbackHandler, EventHandler, OpError
    from punt_lux.hub_client import ConnectHandler
    from punt_lux.operations import FrameRaise, Ok

__all__ = ["FrameRaiseClient", "HubListener", "ListenerFactory", "MenuClient"]


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

    def register_callback(self, callback_id: str, label: str) -> Ok | OpError:
        """Register a menu entry, returning success or a typed error."""
        ...


@runtime_checkable
class FrameRaiseClient(Protocol):
    """The REST surface that brings one frame to the front of the display."""

    def raise_frame(self, frame_id: str) -> FrameRaise | OpError:
        """Raise a frame, reporting whether it was raised or a typed error."""
        ...


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
