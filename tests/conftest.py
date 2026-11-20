"""Isolate every test from the developer's real ``~/.punt-labs`` home."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture(autouse=True)
def private_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point ``HOME`` at a scratch directory and undo any entry-point logging.

    The CLI callback and the MCP lifespan configure the process's diagnostics
    and open usage capture under ``~/.punt-labs/z-spec``; without this, every
    in-process CLI test would write the real log and telemetry store and leave
    the root logger pointed at it for the rest of the run.

    Yields:
        The scratch home directory.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("PUNT_TELEMETRY", raising=False)
    monkeypatch.delenv("Z_SPEC_TELEMETRY", raising=False)
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield home
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)
