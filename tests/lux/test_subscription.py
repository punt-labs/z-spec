"""Humble-object tests for ZSpecSubscription — routing, registration, loop safety.

No live Hub: a fake registrar, a fake listener factory, and a click runner over a
fake Display drive the receive leg. luxd raises the clicked entry's frame
Display-locally (punt-lux DES-088), so the subscription passes each entry's
scene as ``frame_id`` at registration and the click itself only renders. Async
tests run on a throwaway loop via ``asyncio.run``. What a click then *does* is
covered in ``test_click.py``.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from punt_lux import HubUnavailableError
from punt_observe.logging import configure_logging

from punt_zspec.commands.picker import PickerResult
from punt_zspec.commands.result import CommandResult
from punt_zspec.lux import subscription as subscription_mod
from punt_zspec.lux.click import ZSpecClickRunner
from punt_zspec.lux.entry import ZSpecMenuEntries, ZSpecMenuEntry
from punt_zspec.lux.subscription import ZSpecSubscription

if TYPE_CHECKING:
    from collections.abc import Callable

    from punt_lux import CallbackHandler, EventHandler
    from punt_lux.hub_client import ConnectHandler
    from pytest import LogCaptureFixture, MonkeyPatch

    from punt_zspec.commands.show import Display
    from punt_zspec.lux.command_ports import ClickCommand, ClickOutcome
    from punt_zspec.lux.ports import HubListener, ListenerFactory

_MANIFEST = Path("plugin/tutorials/intro/manifest.toml")
_PROJECT = Path("/work/repo")

# A real CommandResult (PickerResult satisfies JsonObject) stands in for a
# successful click outcome; ClickOutcome is satisfied structurally via ``error``.
_OK: ClickOutcome = CommandResult.ok(PickerResult(total=1, scene_id="z-spec-picker"))


class _UnusedDisplay:
    """A Display no successful click touches — only a failed render reports."""

    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        raise AssertionError("no routing test renders an error scene")


class _RecordingMenu:
    """A MenuRegistrar recording each (callback_id, label, frame_id) registration."""

    def __init__(self) -> None:
        self.registered: list[tuple[str, str, str]] = []

    async def register(self, callback_id: str, label: str, frame_id: str) -> None:
        self.registered.append((callback_id, label, frame_id))


def _unused_listen(
    *,
    on_callback: CallbackHandler,
    on_event: EventHandler,
    on_connect: ConnectHandler,
) -> HubListener:
    raise AssertionError("the listener factory must not be called in these tests")


class _RecordingListener:
    """A HubListener that fires on_connect on connect, then waits for stop()."""

    def __init__(self, on_connect: ConnectHandler) -> None:
        self._on_connect = on_connect
        self._stopped = asyncio.Event()

    def subscribe(self, *topics: str) -> None:
        raise AssertionError("z-spec subscribes to no topics")

    async def listen(self) -> None:
        # ConnectHandler admits a sync handler; z-spec's is async, and punt_lux
        # awaits whichever it was handed — so this fake must too.
        handled = self._on_connect()
        if handled is not None:
            await handled
        await self._stopped.wait()

    def stop(self) -> None:
        self._stopped.set()


def _listen_factory(made: list[_RecordingListener]) -> ListenerFactory:
    """Return a ListenerFactory that records every listener it builds."""

    def make(
        *,
        on_callback: CallbackHandler,
        on_event: EventHandler,
        on_connect: ConnectHandler,
    ) -> HubListener:
        listener = _RecordingListener(on_connect)
        made.append(listener)
        return listener

    return make


async def _until(predicate: Callable[[], bool], what: str) -> None:
    """Await *predicate* becoming true, or fail — the leg runs on its own task."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + 2.0
    while not predicate():
        if loop.time() > deadline:
            raise AssertionError(f"{what} never happened")
        await asyncio.sleep(0.01)


def _entry(
    callback_id: str, title: str, target: Path, log: list[tuple[Path, str]]
) -> ZSpecMenuEntry:
    class _Command:
        def run(
            self, path: Path, /, *, frame_id: str, frame_title: str
        ) -> ClickOutcome:
            log.append((path, frame_id))
            return _OK

    def factory(_display: Display) -> ClickCommand:
        return _Command()

    return ZSpecMenuEntry(
        callback_id=callback_id,
        title=title,
        scene_id=callback_id,
        factory=factory,
        target=target,
    )


def _entries(
    tutorial_log: list[tuple[Path, str]], browse_log: list[tuple[Path, str]]
) -> tuple[ZSpecMenuEntry, ...]:
    return (
        _entry("z-spec-tutorial", "Z-Spec Tutorial", _MANIFEST, tutorial_log),
        _entry("z-spec-browse", "Z-Spec Browser", _PROJECT, browse_log),
    )


def _runner() -> ZSpecClickRunner:
    return ZSpecClickRunner(_UnusedDisplay())


def _subscription(
    menu: _RecordingMenu | None = None,
    tutorial_log: list[tuple[Path, str]] | None = None,
    browse_log: list[tuple[Path, str]] | None = None,
    *,
    enabled: bool = True,
) -> ZSpecSubscription:
    return ZSpecSubscription(
        entries=_entries(
            tutorial_log if tutorial_log is not None else [],
            browse_log if browse_log is not None else [],
        ),
        menu=menu if menu is not None else _RecordingMenu(),
        listen=_unused_listen,
        click=_runner(),
        is_enabled=lambda: enabled,
    )


def test_unexpected_topic_event_logs_only_fixed_metadata() -> None:
    path = configure_logging("z-spec", "mcp", level="DEBUG")
    asyncio.run(
        _subscription().on_event(
            "synthetic-private-topic", {"message": "synthetic-private-body"}
        )
    )

    text = path.read_text(encoding="utf-8")
    assert "synthetic-private-topic" not in text
    assert "synthetic-private-body" not in text
    assert (
        "[DEBUG] punt_zspec.lux.subscription: "
        "ignoring Lux topic event: reason=no_topic_subscriptions" in text
    )


def test_tutorial_click_runs_the_tutorial_command_with_matching_scene_id() -> None:
    async def scenario() -> list[tuple[Path, str]]:
        tut: list[tuple[Path, str]] = []
        sub = _subscription(tutorial_log=tut)
        await sub.on_callback("z-spec-tutorial")
        return tut

    tut = asyncio.run(scenario())

    # The command renders into the SAME id luxd raised on click — one Hub scene.
    assert tut == [(_MANIFEST, "z-spec-tutorial")]


def test_browse_click_runs_the_picker_command_on_the_project() -> None:
    async def scenario() -> list[tuple[Path, str]]:
        brw: list[tuple[Path, str]] = []
        sub = _subscription(browse_log=brw)
        await sub.on_callback("z-spec-browse")
        return brw

    brw = asyncio.run(scenario())

    assert brw == [(_PROJECT, "z-spec-browse")]


def test_unknown_callback_is_a_noop() -> None:
    async def scenario() -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
        tut: list[tuple[Path, str]] = []
        brw: list[tuple[Path, str]] = []
        sub = _subscription(tutorial_log=tut, browse_log=brw)
        await sub.on_callback("nope")
        return tut, brw

    tut, brw = asyncio.run(scenario())

    assert (tut, brw) == ([], [])


def test_unknown_callback_logs_only_fixed_metadata() -> None:
    path = configure_logging("z-spec", "mcp", level="DEBUG")
    asyncio.run(_subscription().on_callback("synthetic-private-callback-id"))

    text = path.read_text(encoding="utf-8")
    assert "synthetic-private-callback-id" not in text
    assert (
        "[DEBUG] punt_zspec.lux.subscription: "
        "ignoring Lux callback: reason=unknown_menu_entry" in text
    )


def test_on_connect_registers_both_entries_with_their_scene_as_frame_id() -> None:
    async def scenario() -> list[tuple[str, str, str]]:
        menu = _RecordingMenu()
        sub = ZSpecSubscription(
            entries=ZSpecMenuEntries.of(
                tutorial_manifest=_MANIFEST, browse_root=_PROJECT
            ),
            menu=menu,
            listen=_unused_listen,
            click=_runner(),
            is_enabled=lambda: True,
        )
        await sub.on_connect()
        return menu.registered

    registered = asyncio.run(scenario())

    # The label luxd shows is the entry's one title; the frame_id is its scene,
    # which luxd raises Display-locally on click (DES-088).
    assert registered == [
        ("z-spec-tutorial", "Z-Spec Tutorial", "z-spec-tutorial"),
        ("z-spec-browse", "Z-Spec Browser", "z-spec-picker"),
    ]


def test_on_connect_registers_nothing_where_z_spec_is_not_enabled() -> None:
    """A repo with no marker contributes no entries to the shared lux window.

    on_connect fires on every handshake, so this is also what keeps a repo
    disabled mid-session from having its entries put back by a reconnect after
    a luxd restart.
    """

    async def scenario() -> list[tuple[str, str, str]]:
        menu = _RecordingMenu()
        sub = _subscription(menu=menu, enabled=False)
        await sub.on_connect()
        return menu.registered

    assert asyncio.run(scenario()) == []


def test_a_click_dispatches_nothing_where_z_spec_is_not_enabled() -> None:
    """A stale entry must be inert, not merely unregistered.

    The lux lease keeps an entry on the shared window after the marker goes, so
    the click that follows a `disable` still arrives. It must run no command —
    the same answer the gated tools give.
    """

    async def scenario() -> list[tuple[Path, str]]:
        brw: list[tuple[Path, str]] = []
        sub = _subscription(browse_log=brw, enabled=False)
        await sub.on_callback("z-spec-browse")
        return brw

    path = configure_logging("z-spec", "mcp", level="DEBUG")
    assert asyncio.run(scenario()) == []
    text = path.read_text(encoding="utf-8")
    assert "z-spec-browse" not in text
    assert (
        "[INFO] punt_zspec.lux.subscription: "
        "ignoring Lux callback: reason=z_spec_disabled" in text
    )


def test_enablement_is_re_read_per_click_not_captured_at_registration() -> None:
    """Turning z-spec off mid-session must silence the entries already on screen."""

    async def scenario() -> tuple[int, int]:
        enabled = True
        brw: list[tuple[Path, str]] = []
        sub = ZSpecSubscription(
            entries=_entries([], brw),
            menu=_RecordingMenu(),
            listen=_unused_listen,
            click=_runner(),
            is_enabled=lambda: enabled,
        )
        await sub.on_callback("z-spec-browse")
        before = len(brw)
        enabled = False
        await sub.on_callback("z-spec-browse")
        return before, len(brw)

    before, after = asyncio.run(scenario())

    assert (before, after) == (1, 1)


def test_on_event_is_a_noop() -> None:
    async def scenario() -> None:
        sub = _subscription()
        # z-spec subscribes to no topics; a stray event must never raise.
        await sub.on_event("music.play", {"album": "x"})

    asyncio.run(scenario())


def test_stop_is_safe_before_any_connection() -> None:
    sub = _subscription()

    sub.stop()  # no listener built yet — must not raise


def test_a_stopped_subscription_runs_again_when_restarted() -> None:
    """A stop/start cycle must genuinely restart the receive leg.

    The session holds one subscription for the life of the process and reuses it
    across start/stop, so a ``_stopped`` flag that stayed set would make the
    second run() exit before its first connect: a task that lives, a leg that
    never receives, and a menu that never re-registers — silently.
    """

    async def scenario() -> tuple[int, list[tuple[str, str, str]]]:
        made: list[_RecordingListener] = []
        menu = _RecordingMenu()
        sub = ZSpecSubscription(
            entries=_entries([], []),
            menu=menu,
            listen=_listen_factory(made),
            click=_runner(),
            is_enabled=lambda: True,
        )

        first = asyncio.create_task(sub.run())
        await _until(lambda: len(menu.registered) == 2, "the first registration")
        sub.stop()
        await asyncio.wait_for(first, timeout=2)

        second = asyncio.create_task(sub.run())
        await _until(lambda: len(menu.registered) == 4, "the re-registration")
        sub.stop()
        await asyncio.wait_for(second, timeout=2)

        return len(made), menu.registered

    listeners, registered = asyncio.run(scenario())

    # A second connection, and both entries registered on each of them.
    assert listeners == 2
    assert [callback_id for callback_id, _, _ in registered] == [
        "z-spec-tutorial",
        "z-spec-browse",
        "z-spec-tutorial",
        "z-spec-browse",
    ]


_LOGGER = "punt_zspec.lux.outage"


def _failing_then_listening(
    failures: int, made: list[_RecordingListener], fault: Exception
) -> ListenerFactory:
    """Return a ListenerFactory that raises *fault* *failures* times, then connects."""
    attempts = 0

    def make(
        *,
        on_callback: CallbackHandler,
        on_event: EventHandler,
        on_connect: ConnectHandler,
    ) -> HubListener:
        nonlocal attempts
        attempts += 1
        if attempts <= failures:
            raise fault
        listener = _RecordingListener(on_connect)
        made.append(listener)
        return listener

    return make


def _outage_subscription(listen: ListenerFactory) -> ZSpecSubscription:
    return ZSpecSubscription(
        entries=_entries([], []),
        menu=_RecordingMenu(),
        listen=listen,
        click=_runner(),
        is_enabled=lambda: True,
    )


def _leg_records(caplog: LogCaptureFixture) -> list[tuple[int, str]]:
    return [(r.levelno, r.getMessage()) for r in caplog.records if r.name == _LOGGER]


def test_an_outage_that_recovers_warns_once_and_summarizes_once(
    monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """A down luxd is one WARNING, quiet DEBUG repeats, and one recovered INFO."""
    monkeypatch.setattr(subscription_mod, "_RETRY_SECONDS", 0.0)
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    made: list[_RecordingListener] = []
    sub = _outage_subscription(
        _failing_then_listening(4, made, HubUnavailableError("luxd not running"))
    )

    async def scenario() -> None:
        task = asyncio.create_task(sub.run())
        await _until(lambda: bool(made), "the reconnect")
        await _until(
            lambda: any("outcome=" in m for _, m in _leg_records(caplog)),
            "the recovery summary",
        )
        sub.stop()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(scenario())

    records = _leg_records(caplog)
    assert [m for lvl, m in records if lvl >= logging.WARNING] == [
        "[lux] luxd is down; retrying the z-spec menu leg every 0.0s "
        "(repeats logged at DEBUG)"
    ]
    assert sum(1 for lvl, _ in records if lvl == logging.DEBUG) == 3
    assert [m for lvl, m in records if lvl == logging.INFO] == [
        "[lux] z-spec menu leg outcome=recovered failures=4"
    ]


def test_an_outage_cut_short_by_shutdown_summarizes_as_terminated(
    monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    """Cancelling the leg mid-outage still closes it with one summary."""
    monkeypatch.setattr(subscription_mod, "_RETRY_SECONDS", 0.0)
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    made: list[_RecordingListener] = []
    sub = _outage_subscription(
        _failing_then_listening(10**9, made, HubUnavailableError("luxd not running"))
    )

    async def scenario() -> None:
        task = asyncio.create_task(sub.run())
        await _until(lambda: len(_leg_records(caplog)) >= 3, "several retries")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())

    records = _leg_records(caplog)
    assert sum(1 for lvl, _ in records if lvl >= logging.WARNING) == 1
    summaries = [m for lvl, m in records if lvl == logging.INFO]
    assert len(summaries) == 1
    assert summaries[0].startswith("[lux] z-spec menu leg outcome=terminated failures=")


def test_an_unexpected_fault_opens_the_outage_at_error_with_its_traceback(
    monkeypatch: MonkeyPatch, caplog: LogCaptureFixture
) -> None:
    monkeypatch.setattr(subscription_mod, "_RETRY_SECONDS", 0.0)
    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    made: list[_RecordingListener] = []
    sub = _outage_subscription(_failing_then_listening(3, made, RuntimeError("boom")))

    async def scenario() -> None:
        task = asyncio.create_task(sub.run())
        await _until(lambda: bool(made), "the reconnect")
        sub.stop()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(scenario())

    loud = [
        r for r in caplog.records if r.name == _LOGGER and r.levelno >= logging.WARNING
    ]
    assert [r.levelno for r in loud] == [logging.ERROR]
    assert loud[0].exc_info is not None


def test_stop_during_listener_handoff(monkeypatch: MonkeyPatch) -> None:
    made: list[_RecordingListener] = []
    menu = _RecordingMenu()
    sub = ZSpecSubscription(
        entries=_entries([], []),
        menu=menu,
        listen=_listen_factory(made),
        click=_runner(),
        is_enabled=lambda: True,
    )
    to_thread = asyncio.to_thread

    async def scenario() -> None:
        built = asyncio.Event()
        release = asyncio.Event()

        async def held_handoff[**P](
            factory: Callable[P, HubListener], /, *args: P.args, **kwargs: P.kwargs
        ) -> HubListener:
            listener = await to_thread(factory, *args, **kwargs)
            built.set()
            await release.wait()
            return listener

        monkeypatch.setattr(asyncio, "to_thread", held_handoff)
        task = asyncio.create_task(sub.run())
        await asyncio.wait_for(built.wait(), timeout=2)
        sub.stop()
        release.set()
        await asyncio.wait_for(task, timeout=2)

    asyncio.run(scenario())

    assert len(made) == 1
    assert not menu.registered
