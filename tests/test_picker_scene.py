"""Tests for punt_zspec.picker_scene — the spec picker's summary line and tabs."""

from __future__ import annotations

from pathlib import Path

from punt_lux.protocol import TabBarElement, TextElement

from punt_zspec.picker_scene import build_spec_picker
from punt_zspec.types import BlockKind, SpecModel, ZBlock

_ROOT = Path("/z-spec-fixtures/specs")  # absolute, outside the test cwd


def _make_spec() -> SpecModel:
    return SpecModel(
        title="Test",
        sections=["State"],
        blocks=[
            ZBlock(
                kind=BlockKind.schema,
                name="State",
                declarations=r"x : \nat",
                predicates=r"x \leq 10",
                section="State",
                line_number=20,
            ),
        ],
        source_path="test.tex",
    )


def test_spec_picker_labels_tabs_by_filename_stem() -> None:
    """The picker labels each tab by the spec's filename stem.

    A stem (``a``, ``b``) reads cleanly in a narrow tab strip and never raises —
    discovery globs absolute paths whenever the search directory is absolute
    (Claude Code passes absolute paths by convention), so a ``relative_to(cwd)``
    label would crash for any root the process was not launched from.
    """
    spec = _make_spec()

    scene = build_spec_picker(
        [(_ROOT / "a.tex", spec), (_ROOT / "nested" / "b.tex", spec)], _ROOT
    )

    tab_bar = scene.children[-1]
    assert isinstance(tab_bar, TabBarElement)
    assert [t.label for t in tab_bar.tabs] == ["a", "b"]


def test_spec_picker_summary_names_the_count_and_the_root() -> None:
    """The frame title is a constant, so only the scene can say what was searched.

    Two projects otherwise raise windows that read identically — the gap left
    when the dynamic "Z Specs: <dir>" frame title became a fixed one.
    """
    spec = _make_spec()

    scene = build_spec_picker([(_ROOT / "a.tex", spec), (_ROOT / "b.tex", spec)], _ROOT)

    summary = scene.children[0]
    assert isinstance(summary, TextElement)
    assert summary.content == "2 specs · /z-spec-fixtures/specs"


def test_spec_picker_summary_says_one_spec_not_one_specs() -> None:
    scene = build_spec_picker([(_ROOT / "a.tex", _make_spec())], _ROOT)

    summary = scene.children[0]
    assert isinstance(summary, TextElement)
    assert summary.content == "1 spec · /z-spec-fixtures/specs"


def test_the_summary_sits_above_the_tabs() -> None:
    # Reading order: what was searched, then what was found.
    scene = build_spec_picker([(_ROOT / "a.tex", _make_spec())], _ROOT)

    assert [type(child).__name__ for child in scene.children] == [
        "TextElement",
        "TabBarElement",
    ]
