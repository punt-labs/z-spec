"""Tutorial browser: builds a tabbed lux scene for Z spec collections.

All lessons are loaded upfront and rendered as tabs in a single TabBarElement —
one Tab per lesson, its children being the lesson's annotation plus the spec's
own tab view. The display owns the active tab (Hub-authoritative), so switching
lessons is display-side and needs no MCP round-trip.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

from punt_lux.protocol import (
    CollapsingHeaderElement,
    Element,
    SeparatorElement,
    TabBarElement,
    TextElement,
)
from punt_lux.protocol.elements import Tab

from punt_zspec.applet import build_z_spec_scene
from punt_zspec.types import Collection, Lesson, SpecModel


def _apply_highlights(elements: list[Element], highlights: list[str]) -> list[Element]:
    """Walk element tree and open matching CollapsingHeaders."""
    result: list[Element] = []
    for el in elements:
        if isinstance(el, CollapsingHeaderElement) and any(
            h in el.label for h in highlights
        ):
            result.append(
                CollapsingHeaderElement(
                    id=el.id,
                    label=el.label,
                    open=True,
                    children=el.children,
                )
            )
        else:
            result.append(el)
    return result


def _highlighted_spec_tabs(
    spec_tabs: TabBarElement, highlights: list[str]
) -> TabBarElement:
    """Return a copy of ``spec_tabs`` with the first tab's headers opened.

    TabBarElement and Tab are immutable in 0.21, so the highlight is applied by
    rebuilding the first tab and the bar, never by mutating in place.
    """
    if not spec_tabs.tabs:
        return spec_tabs
    first = spec_tabs.tabs[0]
    # cast (PY-TS-12): Tab.children is the Element ABC tuple; _apply_highlights
    # operates on the protocol Element union — the same runtime objects.
    children = cast("list[Element]", list(first.children))
    new_first = Tab(
        tab_id=first.tab_id,
        label=first.label,
        children=tuple(_apply_highlights(children, highlights)),
    )
    return TabBarElement(id=spec_tabs.id, tabs=(new_first, *spec_tabs.tabs[1:]))


def _build_lesson_page(
    lesson: Lesson,
    spec: SpecModel,
    tex_path: Path,
) -> list[Element]:
    """Build one lesson's content: annotation text followed by the spec tabs."""
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
        id_prefix=f"l{lesson.order}-",
    )

    if lesson.highlights:
        spec_tabs = _highlighted_spec_tabs(spec_tabs, lesson.highlights)

    elements.append(spec_tabs)
    return elements


def build_browser_scene(
    collection: Collection,
    specs: list[tuple[SpecModel, Path]],
) -> TabBarElement:
    """Build the browser scene: one tab per lesson, switched by the display.

    Args:
        collection: Parsed manifest with lessons.
        specs: Parallel list of (SpecModel, tex_path) for each lesson.

    Returns:
        A TabBarElement whose active tab the Hub owns — lesson navigation is
        display-side, needing no round-trip to z-spec.
    """
    tabs: list[Tab] = []
    for idx, (lesson, (spec, tex_path)) in enumerate(
        zip(collection.lessons, specs, strict=True)
    ):
        page = _build_lesson_page(lesson, spec, tex_path)
        label = f"{idx + 1}. {lesson.title}"
        tabs.append(Tab(f"lesson-{lesson.order}", label, tuple(page)))

    return TabBarElement(id="z-spec-browser-tabs", tabs=tabs)


def build_spec_picker(
    specs: list[tuple[Path, SpecModel]],
) -> TabBarElement:
    """Build a tabbed picker for discovered Z specs — one tab per spec.

    Each tab shows the spec's tab view (Spec/Fuzz/ProB/etc.); the display
    switches specs by its active tab, listing them by filename.
    """
    from punt_zspec.report import load_audit, load_fuzz, load_partition, load_report

    tabs: list[Tab] = []
    for idx, (tex_path, spec) in enumerate(specs):
        label = str(
            tex_path.relative_to(Path.cwd()) if tex_path.is_absolute() else tex_path
        )
        spec_tabs = build_z_spec_scene(
            tex_path,
            spec,
            report=load_report(tex_path),
            fuzz=load_fuzz(tex_path),
            partition=load_partition(tex_path),
            audit=load_audit(tex_path),
            id_prefix=f"s{idx}-",
        )
        tabs.append(Tab(f"spec-{idx}", label, (spec_tabs,)))

    return TabBarElement(id="z-spec-picker-tabs", tabs=tabs)
