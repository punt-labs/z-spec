"""Tests for ZSpecLuxClients — both legs are built from one shared app identity."""

from __future__ import annotations

from typing import TYPE_CHECKING

from punt_zspec.lux.clients import ZSpecLuxClients
from punt_zspec.lux.identity import ZSpecLuxIdentity

if TYPE_CHECKING:
    from pytest import MonkeyPatch

_FOR_IDENTITY = "punt_zspec.lux.clients.LuxRestClient.for_identity"
_LISTENER = object()


def test_rest_builds_a_client_for_the_app_identity(monkeypatch: MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_for_identity(identity: object, *, timeout: float = 2.0) -> object:
        captured["identity"] = identity
        return object()

    monkeypatch.setattr(_FOR_IDENTITY, fake_for_identity)
    clients = ZSpecLuxClients(identity=ZSpecLuxIdentity("repo", 7))

    clients.rest()

    identity = captured["identity"]
    assert getattr(identity, "kind", None) == "app"
    assert getattr(identity, "name", None) == "z-spec · repo · #7"
    assert getattr(identity, "lease_ttl", None) == 30.0


def test_listen_wires_the_handlers_onto_the_shared_client(
    monkeypatch: MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class _FakeClient:
        def listener(
            self, *, on_callback: object, on_event: object, on_connect: object
        ) -> object:
            seen["handlers"] = (on_callback, on_event, on_connect)
            return _LISTENER

    def fake_for_identity(*_a: object, **_k: object) -> object:
        return _FakeClient()

    monkeypatch.setattr(_FOR_IDENTITY, fake_for_identity)
    clients = ZSpecLuxClients(identity=ZSpecLuxIdentity("repo", 7))

    async def cb(_id: str) -> None: ...
    async def ev(_t: str, _p: object) -> None: ...
    async def cn() -> None: ...

    result = clients.listen(on_callback=cb, on_event=ev, on_connect=cn)

    # The listener rides on a REST client of the same identity, and the receive
    # handlers are passed straight through.
    assert result is _LISTENER
    assert seen["handlers"] == (cb, ev, cn)
