"""Humble-object tests for BrowseCommand — fake parsers/builder/display."""

from __future__ import annotations

from pathlib import Path

import pytest

from punt_zspec.commands.browse import BrowseCommand, BrowseResult
from punt_zspec.commands.result import CommandFailure
from punt_zspec.commands.show import Display, DisplayError
from punt_zspec.types import Collection, Lesson, SpecModel

_SCENE = object()
_MODEL = SpecModel(title="t", sections=[], blocks=[], source_path="01.tex")


def _model(_path: Path) -> SpecModel:
    return _MODEL


def _collection(base: Path, spec_path: str = "01.tex") -> Collection:
    return Collection(
        title="Test Collection",
        description="",
        lessons=[
            Lesson(
                title="Lesson 1",
                spec_path=spec_path,
                annotation="",
                highlights=[],
                order=0,
            )
        ],
        base_path=base,
    )


def _build_scene(
    _collection: Collection, _specs: list[tuple[SpecModel, Path]]
) -> object:
    return _SCENE


def _unreachable_build(
    _collection: Collection, _specs: list[tuple[SpecModel, Path]]
) -> object:
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


def _manifest(tmp_path: Path) -> Path:
    path = tmp_path / "manifest.toml"
    path.write_text("", encoding="utf-8")
    return path


def test_browse_renders_and_returns_ok(tmp_path: Path) -> None:
    (tmp_path / "01.tex").write_text("dummy", encoding="utf-8")
    manifest = _manifest(tmp_path)
    calls: list[tuple[object, str, str]] = []
    cmd = BrowseCommand(
        build=_build_scene,
        display=_recording_display(calls),
        parse_manifest=lambda _p: _collection(tmp_path),
        parse_spec=_model,
    )

    result = cmd.run(manifest)

    assert result.is_ok
    assert result.unwrap() == BrowseResult(total=1, title="Test Collection")
    assert calls == [(_SCENE, "z-spec-browser", "Test Collection")]


def test_browse_frame_id_override(tmp_path: Path) -> None:
    """A non-default frame_id must reach the display (raise-id == render-id).

    The default path alone cannot catch a hardcoded frame_id, since the default
    equals the literal; the Tutorial callback passes z-spec-tutorial, so the
    render must land there and not on the browse tool's z-spec-browser scene.
    """
    (tmp_path / "01.tex").write_text("dummy", encoding="utf-8")
    manifest = _manifest(tmp_path)
    calls: list[tuple[object, str, str]] = []
    cmd = BrowseCommand(
        build=_build_scene,
        display=_recording_display(calls),
        parse_manifest=lambda _p: _collection(tmp_path),
        parse_spec=_model,
    )

    result = cmd.run(manifest, frame_id="z-spec-tutorial")

    assert result.is_ok
    assert calls == [(_SCENE, "z-spec-tutorial", "Test Collection")]


def test_browse_frame_title_override(tmp_path: Path) -> None:
    """A caller with a name of its own titles the frame with it.

    The menu is that caller: its leaf's label and the frame it raises are one
    string, which no manifest can be made to guarantee. What the command
    *reports* stays the collection's title either way, because that is what the
    collection is called.
    """
    (tmp_path / "01.tex").write_text("dummy", encoding="utf-8")
    manifest = _manifest(tmp_path)
    calls: list[tuple[object, str, str]] = []
    cmd = BrowseCommand(
        build=_build_scene,
        display=_recording_display(calls),
        parse_manifest=lambda _p: _collection(tmp_path),
        parse_spec=_model,
    )

    result = cmd.run(manifest, frame_title="Z-Spec Tutorial")

    assert result.unwrap().title == "Test Collection"
    assert calls == [(_SCENE, "z-spec-browser", "Z-Spec Tutorial")]


def test_browse_ok_wire_format(tmp_path: Path) -> None:
    (tmp_path / "01.tex").write_text("dummy", encoding="utf-8")
    manifest = _manifest(tmp_path)
    cmd = BrowseCommand(
        build=_build_scene,
        display=_recording_display([]),
        parse_manifest=lambda _p: _collection(tmp_path),
        parse_spec=_model,
    )

    expected = '{"ok": true, "total": 1, "title": "Test Collection"}'
    assert cmd.run(manifest).to_json() == expected


def test_browse_manifest_not_found(tmp_path: Path) -> None:
    cmd = BrowseCommand(
        build=_unreachable_build,
        display=_recording_display([]),
        parse_manifest=lambda _p: _collection(tmp_path),
        parse_spec=_model,
    )

    result = cmd.run(tmp_path / "nope.toml")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found
    assert "Manifest not found" in error.message


def test_browse_lesson_spec_missing(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    cmd = BrowseCommand(
        build=_unreachable_build,
        display=_recording_display([]),
        parse_manifest=lambda _p: _collection(tmp_path, spec_path="gone.tex"),
        parse_spec=_model,
    )

    result = cmd.run(manifest)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found
    assert "Spec not found" in error.message


def test_browse_manifest_invalid(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)

    def parse(_path: Path) -> Collection:
        raise ValueError("manifest missing collection.title")

    cmd = BrowseCommand(
        build=_unreachable_build,
        display=_recording_display([]),
        parse_manifest=parse,
        parse_spec=_model,
    )

    result = cmd.run(manifest)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.manifest_invalid
    assert error.message == "manifest missing collection.title"


def test_browse_display_failed(tmp_path: Path) -> None:
    (tmp_path / "01.tex").write_text("dummy", encoding="utf-8")
    manifest = _manifest(tmp_path)
    cmd = BrowseCommand(
        build=_build_scene,
        display=_failing_display("lux down"),
        parse_manifest=lambda _p: _collection(tmp_path),
        parse_spec=_model,
    )

    result = cmd.run(manifest)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.display_failed
    assert result.to_json() == '{"ok": false, "error": "lux down"}'
