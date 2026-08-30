"""Tests for punt_zspec.server_context."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock

import pytest

from punt_zspec.server_context import ServerContext

if TYPE_CHECKING:
    from pathlib import Path


def _bare_context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> ServerContext:
    """Construct one real ServerContext for this test.

    Resets the singleton guard first: the real ``punt_zspec.server`` module
    already constructed the process's one ``ServerContext`` at import time
    (``tests/test_server.py`` triggers that import), so without the reset
    every test here would trip the guard on a construction it never asked
    for. ``EnablementGate`` and ``ZSpecLuxSession`` are cheap and
    lazily-connecting to build for real (see their own docstrings) — no
    network touched by construction alone.
    """
    monkeypatch.setattr(ServerContext, "_constructed", False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    return ServerContext()


# ---------------------------------------------------------------------------
# project_dir
# ---------------------------------------------------------------------------


def test_project_dir_is_the_str_of_the_project_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ctx = _bare_context(monkeypatch, tmp_path)

    assert ctx.project_dir == str(tmp_path)


def test_project_dir_has_no_separate_stored_field(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``project_dir`` derives from ``_project_root`` on every call.

    ``__slots__`` is the proof there's no duplicate cached field — a second
    stored string would need its own slot.
    """
    ctx = _bare_context(monkeypatch, tmp_path)

    assert ServerContext.__slots__ == ("_gate", "_project_root", "_session")
    assert ctx.project_dir == str(ctx._project_root)  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------
# construction order
# ---------------------------------------------------------------------------


def test_gate_is_constructed_before_session_and_wired_to_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The session's constructor needs the gate's ``is_open`` — gate goes first."""
    order: list[str] = []
    gate_instance = MagicMock(name="gate_instance")

    def _fake_gate(directory: Path) -> MagicMock:
        del directory
        order.append("gate")
        return gate_instance

    def _fake_session(is_open: object, cwd: Path | None = None) -> MagicMock:
        del is_open, cwd
        order.append("session")
        return MagicMock(name="session_instance")

    monkeypatch.setattr("punt_zspec.server_context.EnablementGate", _fake_gate)
    monkeypatch.setattr("punt_zspec.server_context.ZSpecLuxSession", _fake_session)
    monkeypatch.setattr(ServerContext, "_constructed", False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    ServerContext()

    assert order == ["gate", "session"]


# ---------------------------------------------------------------------------
# singleton guard
# ---------------------------------------------------------------------------


def test_a_second_construction_in_the_same_process_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _bare_context(monkeypatch, tmp_path)

    with pytest.raises(RuntimeError, match="already constructed"):
        ServerContext()


def test_a_failed_construction_resets_the_guard_and_a_retry_can_succeed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A raise mid-``__new__`` must not brick the singleton guard forever.

    Without the reset, ``_constructed`` stays ``True`` after the failed
    attempt and every subsequent call raises "already constructed" instead
    of the real underlying error — the class can never be retried.
    """
    monkeypatch.setattr(ServerContext, "_constructed", False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))
    monkeypatch.setattr(
        "punt_zspec.server_context.EnablementGate",
        MagicMock(side_effect=RuntimeError("gate init failed")),
    )

    with pytest.raises(RuntimeError, match="gate init failed"):
        ServerContext()

    assert ServerContext._constructed is False  # pyright: ignore[reportPrivateUsage]

    monkeypatch.undo()  # restore the real EnablementGate for the retry
    monkeypatch.setattr(ServerContext, "_constructed", False)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path))

    ServerContext()  # succeeds now that the guard was reset


# ---------------------------------------------------------------------------
# guard / display / sync — narrow delegation to the collaborators
# ---------------------------------------------------------------------------


def test_guard_delegates_to_the_gates_guard(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ctx = _bare_context(monkeypatch, tmp_path)
    gate = MagicMock()
    monkeypatch.setattr(ctx, "_gate", gate)  # pyright: ignore[reportPrivateUsage]
    tool = MagicMock()

    result = ctx.guard(tool)

    gate.guard.assert_called_once_with(tool)
    assert result is gate.guard.return_value


def test_display_delegates_to_the_sessions_display(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ctx = _bare_context(monkeypatch, tmp_path)
    session = MagicMock()
    monkeypatch.setattr(ctx, "_session", session)  # pyright: ignore[reportPrivateUsage]

    assert ctx.display is session.display


def test_sync_delegates_to_the_sessions_sync(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ctx = _bare_context(monkeypatch, tmp_path)
    session = MagicMock()
    session.sync = AsyncMock()
    monkeypatch.setattr(ctx, "_session", session)  # pyright: ignore[reportPrivateUsage]

    asyncio.run(ctx.sync())

    session.sync.assert_awaited_once_with()


# ---------------------------------------------------------------------------
# lifespan — success and exception-during-yield paths
# ---------------------------------------------------------------------------


def test_lifespan_syncs_on_entry_and_stops_on_clean_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    ctx = _bare_context(monkeypatch, tmp_path)
    session = MagicMock()
    session.sync = AsyncMock()
    session.stop = AsyncMock()
    monkeypatch.setattr(ctx, "_session", session)  # pyright: ignore[reportPrivateUsage]

    async def scenario() -> None:
        async with ctx.lifespan(MagicMock()):
            pass

    asyncio.run(scenario())

    session.sync.assert_awaited_once_with()
    session.stop.assert_awaited_once_with()


def test_lifespan_still_stops_when_the_yielded_block_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The ``finally`` still drains the listener; the exception still propagates.

    Closes a pre-existing coverage gap: the original module-level lifespan
    test only ever drove the clean-exit path.
    """
    ctx = _bare_context(monkeypatch, tmp_path)
    session = MagicMock()
    session.sync = AsyncMock()
    session.stop = AsyncMock()
    monkeypatch.setattr(ctx, "_session", session)  # pyright: ignore[reportPrivateUsage]

    async def scenario() -> None:
        async with ctx.lifespan(MagicMock()):
            raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(scenario())

    session.sync.assert_awaited_once_with()
    session.stop.assert_awaited_once_with()
