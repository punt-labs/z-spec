"""Humble-object tests for ZSpecSubscription — routing, registration, loop safety.

No live Hub: a fake registrar, a fake listener factory, and a click runner over a
recording REST client drive the receive leg. Async tests run on a throwaway loop
via ``asyncio.run``. What a click then *does* is covered in ``test_click.py``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from punt_lux.operations import FrameRaise, OpError

from punt_zspec.commands.picker import PickerResult
from punt_zspec.commands.result import CommandResult
from punt_zspec.lux.click import ZSpecClickRunner, ZSpecFrameRaiser
from punt_zspec.lux.entry import ZSpecMenuEntry
from punt_zspec.lux.subscription import ZSpecSubscription

if TYPE_CHECKING:
    from collections.abc import Callable

    from punt_lux import CallbackHandler, EventHandler
    from punt_lux.hub_client import ConnectHandler

    from punt_zspec.commands.show import Display
    from punt_zspec.lux.command_ports import ClickCommand, ClickOutcome
    from punt_zspec.lux.ports import HubListener, ListenerFactory

_MANIFEST = Path("tutorials/intro/manifest.toml")
_PROJECT = Path("/work/repo")

# A real CommandResult (PickerResult satisfies JsonObject) stands in for a
# successful click outcome; ClickOutcome is satisfied structurally via ``error``.
_OK: ClickOutcome = CommandResult.ok(PickerResult(total=1, scene_id="z-spec-picker"))


class _RecordingRaiseClient:
    """A FrameRaiseClient that records each frame a click asked to raise."""

    def __init__(self) -> None:
        self.frames: list[str] = []

    def raise_frame(self, frame_id: str) -> FrameRaise | OpError:
        self.frames.append(frame_id)
        return FrameRaise(frame_id=frame_id, raised=True)


class _UnusedDisplay:
    """A Display no successful click touches — only a failed render reports."""

    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
        raise AssertionError("no routing test renders an error scene")


class _RecordingMenu:
    """A MenuRegistrar that records each (callback_id, label) registration."""

    def __init__(self) -> None:
        self.registered: list[tuple[str, str]] = []

    async def register(self, callback_id: str, label: str) -> None:
        self.registered.append((callback_id, label))


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
    callback_id: str, label: str, target: Path, log: list[tuple[Path, str]]
) -> ZSpecMenuEntry:
    class _Command:
        def run(self, path: Path, /, *, frame_id: str) -> ClickOutcome:
            log.append((path, frame_id))
            return _OK

    def factory(_display: Display) -> ClickCommand:
        return _Command()

    return ZSpecMenuEntry(
        callback_id=callback_id,
        label=label,
        scene_id=callback_id,
        scene_title=label,
        factory=factory,
        target=target,
    )


def _entries(
    tutorial_log: list[tuple[Path, str]], browse_log: list[tuple[Path, str]]
) -> tuple[ZSpecMenuEntry, ...]:
    return (
        _entry("z-spec-tutorial", "Tutorial", _MANIFEST, tutorial_log),
        _entry("z-spec-browse", "Browse", _PROJECT, browse_log),
    )


def _runner(client: _RecordingRaiseClient) -> ZSpecClickRunner:
    return ZSpecClickRunner(_UnusedDisplay(), ZSpecFrameRaiser(lambda: client))


def _subscription(
    raise_client: _RecordingRaiseClient,
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
        click=_runner(raise_client),
        is_enabled=lambda: enabled,
    )


def test_tutorial_click_runs_the_tutorial_command_with_matching_scene_id() -> None:
    async def scenario() -> tuple[list[tuple[Path, str]], list[str]]:
        tut: list[tuple[Path, str]] = []
        client = _RecordingRaiseClient()
        sub = _subscription(client, tutorial_log=tut)
        await sub.on_callback("z-spec-tutorial")
        return tut, client.frames

    tut, raised = asyncio.run(scenario())

    # The command renders into the SAME id the click raised — one Hub scene.
    assert tut == [(_MANIFEST, "z-spec-tutorial")]
    assert raised == ["z-spec-tutorial"]


def test_browse_click_runs_the_picker_command_on_the_project() -> None:
    async def scenario() -> tuple[list[tuple[Path, str]], list[str]]:
        brw: list[tuple[Path, str]] = []
        client = _RecordingRaiseClient()
        sub = _subscription(client, browse_log=brw)
        await sub.on_callback("z-spec-browse")
        return brw, client.frames

    brw, raised = asyncio.run(scenario())

    assert brw == [(_PROJECT, "z-spec-browse")]
    assert raised == ["z-spec-browse"]


def test_unknown_callback_is_a_noop() -> None:
    async def scenario() -> tuple[list[tuple[Path, str]], list[tuple[Path, str]], int]:
        tut: list[tuple[Path, str]] = []
        brw: list[tuple[Path, str]] = []
        client = _RecordingRaiseClient()
        sub = _subscription(client, tutorial_log=tut, browse_log=brw)
        await sub.on_callback("nope")
        return tut, brw, len(client.frames)

    tut, brw, raised = asyncio.run(scenario())

    assert (tut, brw, raised) == ([], [], 0)


def test_on_connect_registers_both_entries_under_their_command_labels() -> None:
    async def scenario() -> list[tuple[str, str]]:
        menu = _RecordingMenu()
        sub = _subscription(_RecordingRaiseClient(), menu=menu)
        await sub.on_connect()
        return menu.registered

    registered = asyncio.run(scenario())

    # A leaf is named for the command alone; the submenu it sits in is already
    # labelled with this client's repository.
    assert registered == [
        ("z-spec-tutorial", "Tutorial"),
        ("z-spec-browse", "Browse"),
    ]


def test_on_connect_registers_nothing_where_z_spec_is_not_enabled() -> None:
    """A repo with no marker contributes no entries to the shared lux window.

    on_connect fires on every handshake, so this is also what keeps a repo
    disabled mid-session from having its entries put back by a reconnect after
    a luxd restart.
    """

    async def scenario() -> list[tuple[str, str]]:
        menu = _RecordingMenu()
        sub = _subscription(_RecordingRaiseClient(), menu=menu, enabled=False)
        await sub.on_connect()
        return menu.registered

    assert asyncio.run(scenario()) == []


def test_a_click_dispatches_nothing_where_z_spec_is_not_enabled() -> None:
    """A stale entry must be inert, not merely unregistered.

    The lux lease keeps an entry on the shared window after the marker goes, so
    the click that follows a `disable` still arrives. It must raise nothing and
    run no command — the same answer the gated tools give.
    """

    async def scenario() -> tuple[list[tuple[Path, str]], int]:
        brw: list[tuple[Path, str]] = []
        client = _RecordingRaiseClient()
        sub = _subscription(client, browse_log=brw, enabled=False)
        await sub.on_callback("z-spec-browse")
        return brw, len(client.frames)

    ran, raised = asyncio.run(scenario())

    assert (ran, raised) == ([], 0)


def test_enablement_is_re_read_per_click_not_captured_at_registration() -> None:
    """Turning z-spec off mid-session must silence the entries already on screen."""

    async def scenario() -> tuple[int, int]:
        enabled = True
        brw: list[tuple[Path, str]] = []
        sub = ZSpecSubscription(
            entries=_entries([], brw),
            menu=_RecordingMenu(),
            listen=_unused_listen,
            click=_runner(_RecordingRaiseClient()),
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
        sub = _subscription(_RecordingRaiseClient())
        # z-spec subscribes to no topics; a stray event must never raise.
        await sub.on_event("music.play", {"album": "x"})

    asyncio.run(scenario())


def test_stop_is_safe_before_any_connection() -> None:
    sub = _subscription(_RecordingRaiseClient())

    sub.stop()  # no listener built yet — must not raise


def test_a_stopped_subscription_runs_again_when_restarted() -> None:
    """A stop/start cycle must genuinely restart the receive leg.

    The session holds one subscription for the life of the process and reuses it
    across start/stop, so a ``_stopped`` flag that stayed set would make the
    second run() exit before its first connect: a task that lives, a leg that
    never receives, and a menu that never re-registers — silently.
    """

    async def scenario() -> tuple[int, list[tuple[str, str]]]:
        made: list[_RecordingListener] = []
        menu = _RecordingMenu()
        sub = ZSpecSubscription(
            entries=_entries([], []),
            menu=menu,
            listen=_listen_factory(made),
            click=_runner(_RecordingRaiseClient()),
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
    assert [callback_id for callback_id, _ in registered] == [
        "z-spec-tutorial",
        "z-spec-browse",
        "z-spec-tutorial",
        "z-spec-browse",
    ]
