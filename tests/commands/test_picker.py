"""Humble-object tests for PickerCommand — fake builder, parser, and display."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from punt_zspec.commands.picker import PickerCommand, PickerResult
from punt_zspec.commands.result import CommandFailure
from punt_zspec.commands.show import Display, DisplayError
from punt_zspec.types import SpecModel
from punt_zspec.types.spec import BlockKind, ZBlock

if TYPE_CHECKING:
    from punt_zspec.commands.picker import PickerSceneBuilder

_SCENE = object()

_BLOCK = ZBlock(
    kind=BlockKind.schema,
    name="Foo",
    declarations="x : \\nat",
    predicates="",
    section="State",
    line_number=1,
)


def _fake_parse(path: Path) -> SpecModel:
    """Parse by content marker: SPEC -> a Z spec, BAD -> unparsable, else empty."""
    text = path.read_text(encoding="utf-8")
    if "BAD" in text:
        raise ValueError("unparsable")
    blocks = [_BLOCK] if "SPEC" in text else []
    return SpecModel(
        title=path.stem, sections=["State"], blocks=blocks, source_path=str(path)
    )


def _recording_build(
    captured: list[list[tuple[Path, SpecModel]]],
) -> PickerSceneBuilder:
    def build(specs: list[tuple[Path, SpecModel]], _root: Path) -> object:
        captured.append(specs)
        return _SCENE

    return build


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


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_picker_discovers_and_renders(tmp_path: Path) -> None:
    _write(tmp_path / "a.tex", "SPEC a")
    _write(tmp_path / "b.tex", "SPEC b")
    captured: list[list[tuple[Path, SpecModel]]] = []
    calls: list[tuple[object, str, str]] = []
    cmd = PickerCommand(
        build=_recording_build(captured),
        display=_recording_display(calls),
        parse=_fake_parse,
    )

    result = cmd.run(tmp_path)

    assert result.is_ok
    assert result.unwrap() == PickerResult(total=2, scene_id="z-spec-picker")
    # build receives (Path, SpecModel) tuples — the opposite order to BrowseCommand.
    (specs,) = captured
    assert [p for p, _ in specs] == [tmp_path / "a.tex", tmp_path / "b.tex"]
    assert all(isinstance(m, SpecModel) for _, m in specs)
    assert calls == [(_SCENE, "z-spec-picker", f"Z Specs: {tmp_path.name}")]


def test_picker_wire_format(tmp_path: Path) -> None:
    _write(tmp_path / "a.tex", "SPEC a")
    cmd = PickerCommand(
        build=_recording_build([]), display=_recording_display([]), parse=_fake_parse
    )

    assert (
        cmd.run(tmp_path).to_json()
        == '{"ok": true, "total": 1, "scene_id": "z-spec-picker"}'
    )


def test_picker_default_dir_title_names_resolved_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write(tmp_path / "a.tex", "SPEC a")
    calls: list[tuple[object, str, str]] = []
    cmd = PickerCommand(
        build=_recording_build([]),
        display=_recording_display(calls),
        parse=_fake_parse,
    )
    # The CLI default Path() and MCP default "." are the cwd, whose bare .name is
    # "" — the frame title must resolve to the real directory basename, not
    # "Z Specs: ".
    monkeypatch.chdir(tmp_path)

    cmd.run(Path())

    assert calls[0][2] == f"Z Specs: {tmp_path.resolve().name}"


def test_picker_frame_id_override(tmp_path: Path) -> None:
    _write(tmp_path / "a.tex", "SPEC a")
    calls: list[tuple[object, str, str]] = []
    cmd = PickerCommand(
        build=_recording_build([]),
        display=_recording_display(calls),
        parse=_fake_parse,
    )

    result = cmd.run(tmp_path, frame_id="z-spec-browse")

    assert result.unwrap().scene_id == "z-spec-browse"
    assert calls[0][1] == "z-spec-browse"


def test_picker_skips_templates_includes_and_unparsable(tmp_path: Path) -> None:
    _write(tmp_path / "real.tex", "SPEC real")
    templates = tmp_path / "templates"
    templates.mkdir()
    _write(templates / "preamble.tex", "SPEC preamble")  # skipped: templates dir
    _write(tmp_path / "preamble.tex", "SPEC top-preamble")  # skipped: preamble name
    _write(tmp_path / "include.tex", "just a latex include")  # skipped: no Z blocks
    _write(tmp_path / "broken.tex", "BAD content")  # skipped: parse raises
    captured: list[list[tuple[Path, SpecModel]]] = []
    cmd = PickerCommand(
        build=_recording_build(captured),
        display=_recording_display([]),
        parse=_fake_parse,
    )

    result = cmd.run(tmp_path)

    assert result.is_ok
    assert result.unwrap().total == 1
    (specs,) = captured
    assert [p.name for p, _ in specs] == ["real.tex"]


def test_picker_empty_dir_is_not_found(tmp_path: Path) -> None:
    _write(tmp_path / "include.tex", "no z blocks here")
    cmd = PickerCommand(
        build=_recording_build([]), display=_recording_display([]), parse=_fake_parse
    )

    result = cmd.run(tmp_path)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found
    assert "No Z specs found" in error.message


def test_picker_missing_directory_is_not_found(tmp_path: Path) -> None:
    cmd = PickerCommand(
        build=_recording_build([]), display=_recording_display([]), parse=_fake_parse
    )

    result = cmd.run(tmp_path / "nope")

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found
    assert "Not a directory" in error.message


def test_picker_file_argument_is_not_found(tmp_path: Path) -> None:
    tex = _write(tmp_path / "a.tex", "SPEC a")
    cmd = PickerCommand(
        build=_recording_build([]), display=_recording_display([]), parse=_fake_parse
    )

    result = cmd.run(tex)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_not_found


@pytest.mark.parametrize(
    "exc",
    [
        ValueError("bad json"),  # json.JSONDecodeError ⊂ ValueError
        OSError("permission denied"),  # read_text TOCTOU / permission race
        UnicodeDecodeError("utf-8", b"", 0, 1, "corrupt report"),
    ],
)
def test_picker_build_raises_is_spec_unreadable(tmp_path: Path, exc: Exception) -> None:
    _write(tmp_path / "a.tex", "SPEC a")

    def _raising_build(_specs: list[tuple[Path, SpecModel]], _root: Path) -> object:
        raise exc

    cmd = PickerCommand(
        build=_raising_build,
        display=_recording_display([]),
        parse=_fake_parse,
    )

    result = cmd.run(tmp_path)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.spec_unreadable
    assert str(exc) in error.message


def test_picker_display_failed(tmp_path: Path) -> None:
    _write(tmp_path / "a.tex", "SPEC a")
    cmd = PickerCommand(
        build=_recording_build([]),
        display=_failing_display("lux down"),
        parse=_fake_parse,
    )

    result = cmd.run(tmp_path)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.display_failed
    assert result.to_json() == '{"ok": false, "error": "lux down"}'
