"""Tests for ZSpecLuxClients — both legs are built from one shared applet identity."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from punt_zspec.lux.clients import ZSpecLuxClients
from punt_zspec.lux.identity import ZSpecLuxIdentity

if TYPE_CHECKING:
    from pytest import MonkeyPatch

_FOR_IDENTITY = "punt_zspec.lux.clients.LuxClient.for_identity"
_LISTENER = object()
_SYNC = object()
_IDENTITY = ZSpecLuxIdentity(Path("/work/repo"))


class _FakeLuxClient:
    """Stand in for ``LuxClient`` — records what ``for_identity`` was handed."""

    sync = _SYNC
    listener_kwargs: dict[str, object] | None = None

    def listener(
        self,
        *,
        on_callback: object,
        on_event: object,
        on_connect: object,
    ) -> object:
        self.listener_kwargs = {
            "on_callback": on_callback,
            "on_event": on_event,
            "on_connect": on_connect,
        }
        return _LISTENER


def test_rest_builds_a_client_for_the_applet_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    fake = _FakeLuxClient()

    def fake_for_identity(identity: object, *, timeout: float = 2.0) -> object:
        captured["identity"] = identity
        return fake

    monkeypatch.setattr(_FOR_IDENTITY, fake_for_identity)
    clients = ZSpecLuxClients(identity=_IDENTITY)

    result = clients.rest()

    assert captured["identity"] is _IDENTITY.client_identity
    # rest() returns LuxClient.sync — the SyncOps surface — not the client itself.
    assert result is _SYNC


def test_lux_client_builds_a_client_for_the_applet_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    fake = _FakeLuxClient()

    def fake_for_identity(identity: object, *, timeout: float = 2.0) -> object:
        captured["identity"] = identity
        return fake

    monkeypatch.setattr(_FOR_IDENTITY, fake_for_identity)
    clients = ZSpecLuxClients(identity=_IDENTITY)

    result: object = clients.lux_client()

    # LuxDisplay needs the client itself, not client.sync, so that the render
    # callsite can pair client.sync.render(request, ...) with scope=client.scope.
    assert captured["identity"] is _IDENTITY.client_identity
    assert result is fake


def test_listen_builds_a_hub_leg_on_the_applet_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    fake = _FakeLuxClient()

    def fake_for_identity(identity: object, *, timeout: float = 2.0) -> object:
        captured["identity"] = identity
        return fake

    monkeypatch.setattr(_FOR_IDENTITY, fake_for_identity)
    clients = ZSpecLuxClients(identity=_IDENTITY)

    async def cb(_id: str) -> None: ...
    async def ev(_t: str, _p: object) -> None: ...
    async def cn() -> None: ...

    result = clients.listen(on_callback=cb, on_event=ev, on_connect=cn)

    # The receive leg is a LuxHubClient on the applet identity's canonical /ws
    # connection — luxd links a same-identity REST menu registration to it, and
    # links it only because both legs were handed the one identity object.
    # LuxClient.listener owns the LuxHubClient.connect call now; the handlers
    # are passed straight through.
    assert result is _LISTENER
    assert captured["identity"] is _IDENTITY.client_identity
    assert fake.listener_kwargs == {
        "on_callback": cb,
        "on_event": ev,
        "on_connect": cn,
    }
