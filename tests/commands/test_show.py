"""Humble-object tests for ShowCommand — fake builder and display, no lux."""

from __future__ import annotations

from pathlib import Path

import pytest

from punt_zspec.commands.result import CommandFailure
from punt_zspec.commands.show import Display, DisplayError, DisplayResult, ShowCommand
from punt_zspec.types import SpecModel, SpecReports

_SCENE = object()
_MODEL = SpecModel(title="t", sections=[], blocks=[], source_path="s.tex")
_REPORTS = SpecReports(report=None, fuzz=None, partition=None, audit=None)


def _model(_path: Path) -> SpecModel:
    return _MODEL


def _reports(_spec: Path) -> SpecReports:
    return _REPORTS


def _build_scene(_spec: Path, _model: SpecModel, _reports: SpecReports) -> object:
    return _SCENE


def _unreachable_build(_spec: Path, _model: SpecModel, _reports: SpecReports) -> object:
    pytest.fail("builder must not be called")


def _recording_display(calls: list[tuple[object, str, str]]) -> Display:
    class _Rec:
        def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
            calls.append((scene, frame_id, frame_title))

    return _Rec()


def _failing_display(message: str) -> Display:
    class _Fail:
        def show(self, scene: object, *, frame_id: str, frame_title: str) -> None:
            raise DisplayError(message)

    return _Fail()


def test_show_renders_and_returns_ok(spec: Path) -> None:
    calls: list[tuple[object, str, str]] = []
    cmd = ShowCommand(
        build=_build_scene,
        display=_recording_display(calls),
        parse=_model,
        load=_reports,
    )

    result = cmd.run(spec)

    assert result.is_ok
    assert result.unwrap() == DisplayResult(scene_id="z-spec")
    assert calls == [(_SCENE, "z-spec", f"Z-Spec: {spec.name}")]


def test_show_ok_wire_format(spec: Path) -> None:
    cmd = ShowCommand(
        build=_build_scene, display=_recording_display([]), parse=_model, load=_reports
    )

    assert cmd.run(spec).to_json() == '{"ok": true, "scene_id": "z-spec"}'


def test_show_spec_not_found(tmp_path: Path) -> None:
    cmd = ShowCommand(
        build=_unreachable_build,
        display=_recording_display([]),
        parse=_model,
        load=_reports,
    )

    result = cmd.run(tmp_path / "nope.tex")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found


def test_show_spec_unreadable(spec: Path) -> None:
    def parse(_path: Path) -> SpecModel:
        raise OSError("bad read")

    cmd = ShowCommand(
        build=_build_scene, display=_recording_display([]), parse=parse, load=_reports
    )

    result = cmd.run(spec)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_unreadable
    assert "Failed to read spec" in error.message


def test_show_display_failed(spec: Path) -> None:
    cmd = ShowCommand(
        build=_build_scene,
        display=_failing_display("lux down"),
        parse=_model,
        load=_reports,
    )

    result = cmd.run(spec)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.display_failed
    assert result.to_json() == '{"ok": false, "error": "lux down"}'
