"""Tests for ZSpecLuxClients — both legs are built from one shared applet identity."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from punt_zspec.lux.clients import ZSpecLuxClients
from punt_zspec.lux.identity import ZSpecLuxIdentity

if TYPE_CHECKING:
    from pytest import MonkeyPatch

_FOR_IDENTITY = "punt_zspec.lux.clients.LuxRestClient.for_identity"
_CONNECT = "punt_zspec.lux.clients.LuxHubClient.connect"
_LISTENER = object()
_IDENTITY = ZSpecLuxIdentity(Path("/work/repo"))


def test_rest_builds_a_client_for_the_applet_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_for_identity(identity: object, *, timeout: float = 2.0) -> object:
        captured["identity"] = identity
        return object()

    monkeypatch.setattr(_FOR_IDENTITY, fake_for_identity)
    clients = ZSpecLuxClients(identity=_IDENTITY)

    clients.rest()

    assert captured["identity"] is _IDENTITY.client_identity


def test_listen_builds_a_hub_leg_on_the_applet_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_connect(
        identity: object,
        *,
        on_callback: object,
        on_event: object,
        on_connect: object,
    ) -> object:
        seen["identity"] = identity
        seen["handlers"] = (on_callback, on_event, on_connect)
        return _LISTENER

    monkeypatch.setattr(_CONNECT, fake_connect)
    clients = ZSpecLuxClients(identity=_IDENTITY)

    async def cb(_id: str) -> None: ...
    async def ev(_t: str, _p: object) -> None: ...
    async def cn() -> None: ...

    result = clients.listen(on_callback=cb, on_event=ev, on_connect=cn)

    # The receive leg is a LuxHubClient on the applet identity's canonical /ws
    # connection — luxd links a same-identity REST menu registration to it, and
    # links it only because both legs were handed the one identity object. The
    # handlers are passed straight through.
    assert result is _LISTENER
    assert seen["handlers"] == (cb, ev, cn)
    assert seen["identity"] is _IDENTITY.client_identity
