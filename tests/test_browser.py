"""Tests for punt_zspec.browser."""

from __future__ import annotations

from pathlib import Path

from punt_lux.protocol import (
    CollapsingHeaderElement,
    Element,
    SeparatorElement,
    TabBarElement,
    TextElement,
)

from punt_zspec.browser import (
    _apply_highlights,  # pyright: ignore[reportPrivateUsage]
    build_browser_scene,
    build_spec_picker,
)
from punt_zspec.types import (
    BlockKind,
    Collection,
    Lesson,
    SpecModel,
    ZBlock,
)


def _make_collection(base_path: Path) -> Collection:
    return Collection(
        title="Intro to Z",
        description="A progressive tour",
        lessons=[
            Lesson(
                title="Basic Types",
                spec_path="01-basic.tex",
                annotation="Z starts with **basic types**.",
                highlights=["Basic Types"],
                order=0,
            ),
            Lesson(
                title="State Schemas",
                spec_path="02-state.tex",
                annotation="A **state schema** captures data.",
                highlights=["State"],
                order=1,
            ),
            Lesson(
                title="Operations",
                spec_path="03-ops.tex",
                annotation="Operations change state.",
                highlights=["Operations"],
                order=2,
            ),
        ],
        base_path=base_path,
    )


def _make_spec() -> SpecModel:
    return SpecModel(
        title="Test",
        sections=["Basic Types", "State", "Operations"],
        blocks=[
            ZBlock(
                kind=BlockKind.zed,
                name="",
                declarations=r"Color ::= red | green | blue",
                predicates="",
                section="Basic Types",
                line_number=10,
            ),
            ZBlock(
                kind=BlockKind.schema,
                name="State",
                declarations=r"x : \nat",
                predicates=r"x \leq 10",
                section="State",
                line_number=20,
            ),
            ZBlock(
                kind=BlockKind.schema,
                name="Increment",
                declarations=r"\Delta State",
                predicates=r"x' = x + 1",
                section="Operations",
                line_number=30,
            ),
        ],
        source_path="test.tex",
    )


def _make_specs(n: int = 3) -> list[tuple[SpecModel, Path]]:
    spec = _make_spec()
    return [(spec, Path(f"test-{i}.tex")) for i in range(n)]


# ---------------------------------------------------------------------------
# Scene building tests
# ---------------------------------------------------------------------------


def test_scene_is_tab_bar() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    assert isinstance(scene, TabBarElement)
    assert scene.id == "z-spec-browser-tabs"
    assert len(scene.tabs) == 3
    labels = [t.label for t in scene.tabs]
    assert labels == ["1. Basic Types", "2. State Schemas", "3. Operations"]
    assert [t.tab_id for t in scene.tabs] == ["lesson-0", "lesson-1", "lesson-2"]


def test_lesson_tab_has_annotation() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    first_child = scene.tabs[0].children[0]
    assert isinstance(first_child, TextElement)
    assert "basic types" in first_child.content


def test_spec_picker_labels_relative_to_root_for_absolute_dir() -> None:
    """build_spec_picker must not crash on an absolute dir outside the cwd.

    Discovery globs absolute paths whenever the search directory is absolute
    (Claude Code passes absolute paths by convention). Labelling against the
    discovery root — not the process cwd — keeps relative_to valid by
    construction; the old cwd labelling raised ValueError for any root the
    process was not launched from.
    """
    root = Path("/z-spec-fixtures/specs")  # absolute, outside the test cwd
    spec = _make_spec()
    scene = build_spec_picker(
        [(root / "a.tex", spec), (root / "nested" / "b.tex", spec)], root
    )

    assert isinstance(scene, TabBarElement)
    assert [t.label for t in scene.tabs] == ["a.tex", "nested/b.tex"]


def test_lesson_tab_has_spec_tabs() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    spec_tabs = scene.tabs[0].children[-1]
    assert isinstance(spec_tabs, TabBarElement)
    assert spec_tabs.tabs[0].label == "Spec"


def test_lesson_without_annotation() -> None:
    coll = Collection(
        title="Minimal",
        description="",
        lessons=[
            Lesson(
                title="No Annotation",
                spec_path="01.tex",
                annotation="",
                highlights=[],
                order=0,
            ),
        ],
        base_path=Path("/tmp"),
    )
    scene = build_browser_scene(coll, _make_specs(1))

    # No annotation — the lesson tab holds only the spec tabs.
    annotation_ids = [
        e.id for e in scene.tabs[0].children if isinstance(e, TextElement)
    ]
    assert not any(aid.startswith("annotation-") for aid in annotation_ids)


def test_each_lesson_has_unique_annotation_id() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    ids = [
        el.id
        for tab in scene.tabs
        for el in tab.children
        if isinstance(el, TextElement) and el.id.startswith("annotation-")
    ]
    assert len(ids) == 3
    assert len(set(ids)) == 3  # all unique


# ---------------------------------------------------------------------------
# Highlight application tests
# ---------------------------------------------------------------------------


def test_apply_highlights_opens_matching() -> None:
    elements: list[Element] = [
        CollapsingHeaderElement(
            id="sec-basic-types",
            label="Basic Types",
            open=False,
            children=[],
        ),
        CollapsingHeaderElement(
            id="sec-state",
            label="State",
            open=False,
            children=[],
        ),
        CollapsingHeaderElement(
            id="sec-ops",
            label="Operations",
            open=False,
            children=[],
        ),
    ]

    result = _apply_highlights(elements, ["Basic Types", "State"])
    assert isinstance(result[0], CollapsingHeaderElement)
    assert result[0].open is True
    assert isinstance(result[1], CollapsingHeaderElement)
    assert result[1].open is True
    assert isinstance(result[2], CollapsingHeaderElement)
    assert result[2].open is False


def test_apply_highlights_partial_match() -> None:
    elements: list[Element] = [
        CollapsingHeaderElement(
            id="sec-basic",
            label="Basic Types and Constants",
            open=False,
            children=[],
        ),
    ]
    result = _apply_highlights(elements, ["Basic"])
    assert isinstance(result[0], CollapsingHeaderElement)
    assert result[0].open is True


def test_apply_highlights_preserves_non_headers() -> None:
    elements: list[Element] = [
        SeparatorElement(),
        CollapsingHeaderElement(
            id="sec-state",
            label="State",
            open=False,
            children=[],
        ),
    ]
    result = _apply_highlights(elements, ["State"])
    assert isinstance(result[0], SeparatorElement)
    assert isinstance(result[1], CollapsingHeaderElement)
    assert result[1].open is True
