"""``ZSpecLuxClients`` — build z-spec's REST and listener clients from one identity.

The same app identity backs both legs — the REST client that renders scenes and
registers the menu, and the listener that carries the click stream — so luxd
resolves both to one session and a callback registered over REST is delivered on
the listener's stream. ``rest`` raises ``HubUnavailableError`` when luxd is down,
so callers invoke it lazily (the render path) or under a retry (the listener),
never eagerly at startup — a down luxd must never block the MCP tool surface.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from punt_lux import LuxRestClient

from punt_zspec.lux.identity import ZSpecLuxIdentity

if TYPE_CHECKING:
    from punt_lux import CallbackHandler, EventHandler
    from punt_lux.hub_client import ConnectHandler

    from punt_zspec.lux.ports import HubListener

__all__ = ["ZSpecLuxClients"]


@final
class ZSpecLuxClients:
    """Build the REST and listener clients that share one app identity."""

    _identity: ZSpecLuxIdentity
    __slots__ = ("_identity",)

    def __new__(cls, identity: ZSpecLuxIdentity | None = None) -> Self:
        # None (PY-TS-14): the real per-session app identity; tests inject a fixed
        # one. A concrete default, not a missing value.
        self = super().__new__(cls)
        self._identity = (
            identity if identity is not None else ZSpecLuxIdentity.for_session()
        )
        return self

    @property
    def identity(self) -> ZSpecLuxIdentity:
        """Return the app identity backing both legs (for the menu labels)."""
        return self._identity

    def rest(self) -> LuxRestClient:
        """Build a REST client under the app identity, or raise if luxd is down.

        Callers invoke this lazily/under a guard: ``for_identity`` raises
        ``HubUnavailableError`` when luxd is not running, and the render path and
        the menu registrar both swallow that so the tool surface survives.
        """
        return LuxRestClient.for_identity(self._identity.client_identity)

    def listen(
        self,
        *,
        on_callback: CallbackHandler,
        on_event: EventHandler,
        on_connect: ConnectHandler,
    ) -> HubListener:
        """Build the persistent listener leg sharing the app identity.

        The listener rides on a fresh REST client of the same identity, so a
        callback the registrar registers over REST reaches this stream. Raises
        ``HubUnavailableError`` when luxd is down; the subscription's run loop
        retries, so a late-starting luxd is picked up.
        """
        return self.rest().listener(
            on_callback=on_callback, on_event=on_event, on_connect=on_connect
        )
