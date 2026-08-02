"""Where the user's project is — and what the server says when it cannot tell."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from punt_zspec.lux.project import ProjectRoot

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest import MonkeyPatch


def _plugin_launch(monkeypatch: MonkeyPatch, checkout: Path) -> None:
    """Put the process where plugin.json puts it: cwd pinned to the checkout."""
    monkeypatch.setenv("ZSPEC_PLUGIN_ROOT", str(checkout))
    monkeypatch.chdir(checkout)


def test_an_absolute_project_dir_wins_over_the_cwd(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    project = tmp_path / "user-project"
    project.mkdir()
    _plugin_launch(monkeypatch, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))

    assert ProjectRoot.resolve().path == project


def test_no_project_dir_falls_back_to_the_cwd(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # The standalone CLI: no plugin, and the cwd really is the user's project.
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("ZSPEC_PLUGIN_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    assert ProjectRoot.resolve().path == tmp_path


def test_a_relative_project_dir_is_not_a_project_signal(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    # A relative value would resolve against the pinned plugin cwd and name a
    # directory inside the plugin checkout.
    (tmp_path / "sibling").mkdir()
    _plugin_launch(monkeypatch, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "sibling")

    assert ProjectRoot.resolve().path == tmp_path


def test_a_project_dir_that_does_not_exist_is_ignored(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    _plugin_launch(monkeypatch, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(tmp_path / "gone"))

    assert ProjectRoot.resolve().path == tmp_path


def test_the_fallback_warns_under_a_plugin_launch(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Silence here means every tool reads z-spec's own repo and nobody knows.
    _plugin_launch(monkeypatch, tmp_path)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    with caplog.at_level(logging.WARNING, logger="punt_zspec.lux.project"):
        root = ProjectRoot.resolve()

    assert root.path == tmp_path
    assert "CLAUDE_PROJECT_DIR" in caplog.text
    assert str(tmp_path) in caplog.text


def test_the_fallback_is_silent_for_the_standalone_cli(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Without the plugin the cwd is the project, so the fallback is the answer,
    # not a symptom.
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("ZSPEC_PLUGIN_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)

    with caplog.at_level(logging.WARNING, logger="punt_zspec.lux.project"):
        ProjectRoot.resolve()

    assert caplog.text == ""


def test_a_usable_project_dir_warns_about_nothing(
    tmp_path: Path, monkeypatch: MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    project = tmp_path / "user-project"
    project.mkdir()
    _plugin_launch(monkeypatch, tmp_path)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))

    with caplog.at_level(logging.WARNING, logger="punt_zspec.lux.project"):
        ProjectRoot.resolve()

    assert caplog.text == ""
