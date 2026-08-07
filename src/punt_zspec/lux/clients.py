"""``ZSpecLuxClients`` — build z-spec's REST and hub listener clients from one identity.

Both legs share one applet identity, so luxd links a REST-registered menu callback
to the ``LuxHubClient`` listen leg's stream. ``rest`` raises when luxd is down.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from punt_lux import LuxHubClient, LuxRestClient

from punt_zspec.lux.identity import ZSpecLuxIdentity

if TYPE_CHECKING:
    from punt_lux import CallbackHandler, EventHandler
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

    def rest(self) -> LuxRestClient:
        """Build a REST client under the applet identity, or raise if luxd is down.

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
        """Build the persistent hub listen leg sharing the applet identity.

        The leg is a :class:`LuxHubClient` on the identity's canonical ``/ws``
        connection; luxd links a same-identity REST menu registration to it, so a
        click reaches this stream (a leg built from a bare REST client holds no
        ``/ws`` leg and luxd refuses the registration). Raises
        ``HubUnavailableError`` when luxd is down; the run loop retries.
        """
        return LuxHubClient.connect(
            self._identity.client_identity,
            on_callback=on_callback,
            on_event=on_event,
            on_connect=on_connect,
        )
