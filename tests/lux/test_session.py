"""Tests for ZSpecLuxSession — the lifespan starts/stops cleanly, down luxd or not."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from punt_lux import HubUnavailableError

from punt_zspec.lux import session as session_mod
from punt_zspec.lux.clients import ZSpecLuxClients
from punt_zspec.lux.identity import ZSpecLuxIdentity
from punt_zspec.lux.session import ZSpecLuxSession
from punt_zspec.lux.subscription import ZSpecSubscription

if TYPE_CHECKING:
    from pytest import LogCaptureFixture, MonkeyPatch

_FOR_IDENTITY = "punt_zspec.lux.clients.LuxClient.for_identity"


def _luxd_down(*_a: object, **_k: object) -> object:
    """Stand in for the REST client factory when luxd is not running."""
    raise HubUnavailableError("luxd not running")


def _task_of(session: ZSpecLuxSession) -> asyncio.Task[None] | None:
    """Return the session's listener task — the only handle on the receive leg."""
    return session._task  # pyright: ignore[reportPrivateUsage]


def _session(tmp_path: Path, *, enabled: bool = True) -> ZSpecLuxSession:
    return ZSpecLuxSession(
        lambda: enabled,
        clients=ZSpecLuxClients(identity=ZSpecLuxIdentity(Path("/work/repo"))),
        cwd=tmp_path,
        tutorial_manifest=tmp_path / "manifest.toml",
    )


def test_start_then_stop_is_clean_when_luxd_is_down(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(_FOR_IDENTITY, _luxd_down)

    async def scenario() -> object:
        session = _session(tmp_path)
        # A down luxd at startup must be non-fatal: the listener retries and the
        # tool surface keeps working, so start() never raises.
        await session.start()
        await asyncio.sleep(0.05)  # let the listener attempt, fail, and back off
        await session.stop()  # cancel + drain must be clean
        return session.display

    display = asyncio.run(scenario())

    assert type(display).__name__ == "LuxDisplay"


def test_stop_before_start_is_safe(tmp_path: Path) -> None:
    async def scenario() -> None:
        session = _session(tmp_path)
        await session.stop()  # no task spawned yet — must not raise

    asyncio.run(scenario())


def test_second_start_does_not_spawn_a_second_task(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    monkeypatch.setattr(_FOR_IDENTITY, _luxd_down)

    async def scenario() -> None:
        session = _session(tmp_path)
        # A double start() (double lifespan entry / reconnect path) must be
        # idempotent — a second create_task would orphan the first, which stop()
        # can no longer cancel. The guard short-circuits and warns instead.
        await session.start()
        with caplog.at_level(logging.WARNING, logger=session_mod.__name__):
            await session.start()
        await session.stop()

    asyncio.run(scenario())

    assert "already started" in caplog.text


def test_sync_starts_the_leg_where_the_marker_is_present(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(_FOR_IDENTITY, _luxd_down)

    async def scenario() -> bool:
        session = _session(tmp_path, enabled=True)
        await session.sync()
        live = _task_of(session) is not None
        await session.stop()
        return live

    assert asyncio.run(scenario()) is True


def test_sync_stops_the_leg_where_the_marker_is_absent(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setattr(_FOR_IDENTITY, _luxd_down)

    async def scenario() -> object:
        enabled = True
        session = ZSpecLuxSession(
            lambda: enabled,
            clients=ZSpecLuxClients(identity=ZSpecLuxIdentity(Path("/work/repo"))),
            cwd=tmp_path,
            tutorial_manifest=tmp_path / "manifest.toml",
        )
        await session.sync()
        # `/z-spec:disable` removes the marker while the server runs. The next
        # sync must take the connection down, not leave the entries live on the
        # shared window with the tool surface already shut.
        enabled = False
        await session.sync()
        return _task_of(session)

    assert asyncio.run(scenario()) is None


def test_start_replaces_a_listener_task_that_has_died(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    async def die(_self: ZSpecSubscription) -> None:
        raise RuntimeError("the receive leg blew up")

    monkeypatch.setattr(ZSpecSubscription, "run", die)

    async def scenario() -> tuple[bool, bool]:
        session = _session(tmp_path)
        await session.start()
        await asyncio.sleep(0.01)  # let the task run and raise
        first = _task_of(session)
        assert first is not None
        # A task that ended still sits in _task. Guarding only on "is not None"
        # would refuse every later start(), leaving the menu down for the life
        # of the process — a finished task must be replaced, not honoured.
        with caplog.at_level(logging.WARNING, logger=session_mod.__name__):
            await session.start()
        second = _task_of(session)
        await session.stop()
        return first.done(), first is not second

    died, replaced = asyncio.run(scenario())

    assert (died, replaced) == (True, True)
    assert "listener died" in caplog.text
    assert "already started" not in caplog.text


def test_stop_drains_a_listener_that_died_on_its_own(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    async def die(_self: ZSpecSubscription) -> None:
        raise RuntimeError("the receive leg blew up")

    monkeypatch.setattr(ZSpecSubscription, "run", die)

    async def scenario() -> None:
        session = _session(tmp_path)
        await session.start()
        await asyncio.sleep(0.01)
        # Awaiting an already-failed task re-raises its exception; shutdown must
        # consume it, not carry a dead listener's fault out of the lifespan.
        await session.stop()

    asyncio.run(scenario())


def test_default_manifest_prefers_plugin_root(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    manifest = tmp_path / "tutorials" / "intro" / "manifest.toml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("", encoding="utf-8")
    # plugin.json injects ZSPEC_PLUGIN_ROOT=${CLAUDE_PLUGIN_ROOT} for the installed
    # server; the default manifest must resolve under it, not the source tree.
    monkeypatch.setenv("ZSPEC_PLUGIN_ROOT", str(tmp_path))

    resolved = ZSpecLuxSession._default_tutorial_manifest()  # pyright: ignore[reportPrivateUsage]

    assert resolved == manifest


def test_default_manifest_falls_back_to_dev_checkout(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.delenv("ZSPEC_PLUGIN_ROOT", raising=False)
    # Dev src-layout: with no env var, resolve relative to the package — three
    # parents up from src/punt_zspec/lux/session.py is the repo root, and the
    # tutorials live inside the shippable plugin/ directory under it.
    repo_root = Path(session_mod.__file__).resolve().parents[3]
    expected = repo_root / "plugin" / "tutorials" / "intro" / "manifest.toml"

    resolved = ZSpecLuxSession._default_tutorial_manifest()  # pyright: ignore[reportPrivateUsage]

    assert resolved == expected
    # The path is only worth resolving if it names the manifest this repo ships:
    # an assertion that mirrors the implementation would survive a move of the
    # tutorials and leave the Tutorial menu entry silently empty.
    assert resolved.is_file()
