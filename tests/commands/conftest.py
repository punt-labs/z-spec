"""Shared fixtures for command-layer humble-object tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def spec(tmp_path: Path) -> Path:
    """Return the path to an existing empty ``.tex`` spec."""
    path = tmp_path / "s.tex"
    path.write_text("", encoding="utf-8")
    return path
