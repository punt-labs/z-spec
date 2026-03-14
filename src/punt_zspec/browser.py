"""Tutorial browser: builds a paged lux scene for Z spec collections.

All lessons are loaded upfront and rendered as pages in a single GroupElement
with layout="paged". A ComboElement drives page switching client-side —
no MCP round-trips for navigation.
"""

from __future__ import annotations

from pathlib import Path

from punt_lux.protocol import (
    CollapsingHeaderElement,
    ComboElement,
    Element,
    GroupElement,
    SeparatorElement,
    TextElement,
)

from punt_zspec.applet import build_z_spec_scene
from punt_zspec.types import Collection, Lesson, SpecModel


def _apply_highlights(elements: list[Element], highlights: list[str]) -> list[Element]:
    """Walk element tree and set default_open on matching CollapsingHeaders."""
    result: list[Element] = []
    for el in elements:
        if isinstance(el, CollapsingHeaderElement) and any(
            h in el.label for h in highlights
        ):
            result.append(
                CollapsingHeaderElement(
                    id=el.id,
                    label=el.label,
                    default_open=True,
                    children=el.children,
                )
            )
        else:
            result.append(el)
    return result


def _build_lesson_page(
    lesson: Lesson,
    spec: SpecModel,
    tex_path: Path,
) -> list[Element]:
    """Build the content for a single lesson page: annotation + spec tabs."""
    from punt_zspec.report import load_audit, load_fuzz, load_partition, load_report

    elements: list[Element] = []

    annotation = lesson.annotation.strip()
    if annotation:
        elements.append(
            TextElement(
                id=f"annotation-{lesson.order}",
                content=annotation,
            )
        )
        elements.append(SeparatorElement())

    spec_tabs = build_z_spec_scene(
        tex_path,
        spec,
        report=load_report(tex_path),
        fuzz=load_fuzz(tex_path),
        partition=load_partition(tex_path),
        audit=load_audit(tex_path),
    )

    if lesson.highlights and spec_tabs.tabs:
        first_tab = spec_tabs.tabs[0]
        children = first_tab.get("children", [])
        first_tab["children"] = _apply_highlights(children, lesson.highlights)

    elements.append(spec_tabs)
    return elements


def build_browser_scene(
    collection: Collection,
    specs: list[tuple[SpecModel, Path]],
) -> GroupElement:
    """Build the full browser scene: nav bar + paged lesson content.

    Args:
        collection: Parsed manifest with lessons.
        specs: Parallel list of (SpecModel, tex_path) for each lesson.

    Returns:
        A paged GroupElement — combo switches pages client-side.
    """
    # Combo for page selection — display renders Prev/Next buttons around it.
    page_combo = ComboElement(
        id="nav-select",
        label="",
        items=[f"{idx + 1}. {les.title}" for idx, les in enumerate(collection.lessons)],
        selected=0,
    )

    # --- Build all lesson pages ---
    pages: list[list[Element]] = []
    for lesson, (spec, tex_path) in zip(collection.lessons, specs, strict=True):
        pages.append(_build_lesson_page(lesson, spec, tex_path))

    return GroupElement(
        id="browser",
        layout="paged",
        children=[page_combo],
        pages=pages,
        page_source="nav-select",
    )


def build_spec_picker(
    specs: list[tuple[Path, SpecModel]],
) -> GroupElement:
    """Build a paged picker for discovered Z specs.

    Each page shows the spec's tab view (Spec/Fuzz/ProB/etc.).
    The combo lists specs by filename.
    """
    from punt_zspec.report import load_audit, load_fuzz, load_partition, load_report

    page_combo = ComboElement(
        id="spec-select",
        label="",
        items=[
            str(
                tex_path.relative_to(Path.cwd()) if tex_path.is_absolute() else tex_path
            )
            for tex_path, _ in specs
        ],
        selected=0,
    )

    pages: list[list[Element]] = []
    for tex_path, spec in specs:
        spec_tabs = build_z_spec_scene(
            tex_path,
            spec,
            report=load_report(tex_path),
            fuzz=load_fuzz(tex_path),
            partition=load_partition(tex_path),
            audit=load_audit(tex_path),
        )
        pages.append([spec_tabs])

    return GroupElement(
        id="spec-picker",
        layout="paged",
        children=[page_combo],
        pages=pages,
        page_source="spec-select",
    )
