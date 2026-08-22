"""``ZSpecLuxClients`` — build z-spec's REST and hub listener clients from one identity.

Both legs share one applet identity, so luxd links a REST-registered menu callback
to the ``LuxHubClient`` listen leg's stream. ``rest`` raises when luxd is down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from punt_lux import LuxClient

from punt_zspec.lux.identity import ZSpecLuxIdentity

if TYPE_CHECKING:
    from punt_lux import CallbackHandler, EventHandler
    from punt_lux.client._sync_ops import SyncOps
    from punt_lux.hub_client import ConnectHandler

    from punt_zspec.lux.ports import HubListener

__all__ = ["ZSpecLuxClients"]


@final
class ZSpecLuxClients:
    """Build the REST and listener clients that share one applet identity."""

    _identity: ZSpecLuxIdentity
    __slots__ = ("_identity",)

    def __new__(cls, identity: ZSpecLuxIdentity | None = None) -> Self:
        # None (PY-TS-14): the real per-session applet identity; tests inject a
        # fixed one. A concrete default, not a missing value.
        self = super().__new__(cls)
        self._identity = (
            identity if identity is not None else ZSpecLuxIdentity.for_session()
        )
        return self

    def rest(self) -> SyncOps:
        """Return the ``SyncOps`` surface under the applet identity, or raise.

        Callers invoke this lazily/under a guard: ``for_identity`` raises
        ``HubUnavailableError`` when luxd is not running, and the menu registrar
        and frame raiser both swallow that so the tool surface survives. The
        returned ``SyncOps`` is ``LuxClient.sync`` — the same transport typed as
        a Protocol, so ``register_callback(id, label)`` and ``raise_frame(id)``
        keep the sync shapes ``asyncio.to_thread`` wraps.
        """
        return LuxClient.for_identity(self._identity.client_identity).sync

    def lux_client(self) -> LuxClient:
        """Build a ``LuxClient`` under the applet identity, or raise if luxd is down.

        The one caller — :class:`~punt_zspec.display.LuxDisplay` — needs the
        client itself, not the ``SyncOps`` alias, because the render callsite
        pairs ``client.sync.render(request, ...)`` with ``scope=client.scope``.
        """
        return LuxClient.for_identity(self._identity.client_identity)

    def listen(
        self,
        *,
        on_callback: CallbackHandler,
        on_event: EventHandler,
        on_connect: ConnectHandler,
    ) -> HubListener:
        """Build the persistent hub listen leg sharing the applet identity.

        The leg is a :class:`LuxHubClient` on the identity's canonical ``/ws``
        connection; luxd links a same-identity REST menu registration to it, so a
        click reaches this stream (a leg built from a bare REST client holds no
        ``/ws`` leg and luxd refuses the registration). Raises
        ``HubUnavailableError`` when luxd is down; the run loop retries.
        """
        return LuxClient.for_identity(self._identity.client_identity).listener(
            on_callback=on_callback,
            on_event=on_event,
            on_connect=on_connect,
        )
