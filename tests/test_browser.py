"""Tests for punt_zspec.browser."""

from __future__ import annotations

from pathlib import Path

from punt_lux.protocol import (
    CollapsingHeaderElement,
    ComboElement,
    Element,
    GroupElement,
    MarkdownElement,
    SeparatorElement,
    TabBarElement,
)

from punt_zspec.browser import (
    _apply_highlights,  # pyright: ignore[reportPrivateUsage]
    build_browser_scene,
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


def test_scene_is_paged_group() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    assert isinstance(scene, GroupElement)
    assert scene.id == "browser"
    assert scene.layout == "paged"
    assert scene.page_source == "nav-select"
    assert len(scene.pages) == 3


def test_children_has_combo() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    # children = just the combo (display renders Prev/Next around it)
    assert len(scene.children) == 1
    combo = scene.children[0]
    assert isinstance(combo, ComboElement)
    assert combo.id == "nav-select"
    assert len(combo.items) == 3
    assert combo.selected == 0
    assert "1. Basic Types" in combo.items[0]
    assert "2. State Schemas" in combo.items[1]
    assert "3. Operations" in combo.items[2]


def test_page_has_annotation() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    page0 = scene.pages[0]
    annotation = page0[0]
    assert isinstance(annotation, MarkdownElement)
    assert "basic types" in annotation.content


def test_page_has_spec_tabs() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    page0 = scene.pages[0]
    tabs = page0[-1]
    assert isinstance(tabs, TabBarElement)
    assert tabs.tabs[0]["label"] == "Spec"


def test_page_without_annotation() -> None:
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

    page0 = scene.pages[0]
    types = [type(e).__name__ for e in page0]
    assert "MarkdownElement" not in types


def test_each_page_has_unique_annotation_id() -> None:
    coll = _make_collection(Path("/tmp"))
    scene = build_browser_scene(coll, _make_specs())

    ids: list[str] = []
    for page in scene.pages:
        for el in page:
            if isinstance(el, MarkdownElement):
                ids.append(el.id)
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
            default_open=False,
            children=[],
        ),
        CollapsingHeaderElement(
            id="sec-state",
            label="State",
            default_open=False,
            children=[],
        ),
        CollapsingHeaderElement(
            id="sec-ops",
            label="Operations",
            default_open=False,
            children=[],
        ),
    ]

    result = _apply_highlights(elements, ["Basic Types", "State"])
    assert isinstance(result[0], CollapsingHeaderElement)
    assert result[0].default_open is True
    assert isinstance(result[1], CollapsingHeaderElement)
    assert result[1].default_open is True
    assert isinstance(result[2], CollapsingHeaderElement)
    assert result[2].default_open is False


def test_apply_highlights_partial_match() -> None:
    elements: list[Element] = [
        CollapsingHeaderElement(
            id="sec-basic",
            label="Basic Types and Constants",
            default_open=False,
            children=[],
        ),
    ]
    result = _apply_highlights(elements, ["Basic"])
    assert isinstance(result[0], CollapsingHeaderElement)
    assert result[0].default_open is True


def test_apply_highlights_preserves_non_headers() -> None:
    elements: list[Element] = [
        SeparatorElement(),
        CollapsingHeaderElement(
            id="sec-state",
            label="State",
            default_open=False,
            children=[],
        ),
    ]
    result = _apply_highlights(elements, ["State"])
    assert isinstance(result[0], SeparatorElement)
    assert isinstance(result[1], CollapsingHeaderElement)
    assert result[1].default_open is True
