"""Lux applet: builds element tree for Z spec display, connects to lux."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from punt_zspec.parser import render_schema_box
from punt_zspec.report import is_stale
from punt_zspec.types import ProbReport, SpecModel

# Sections that should be open by default (types, constants, state).
_DEFAULT_OPEN_SECTIONS = {
    "Basic Types",
    "Free Types",
    "Constants",
    "Global Constants",
    "State",
}


def _build_spec_tab(spec: SpecModel) -> list[dict[str, Any]]:
    """Build Spec tab elements: schemas grouped by section with collapsing headers."""
    elements: list[dict[str, Any]] = []
    by_section = spec.blocks_by_section()

    for section in spec.sections:
        blocks = by_section.get(section, [])
        if not blocks:
            continue

        children: list[dict[str, Any]] = []
        for block in blocks:
            box_text = render_schema_box(block)
            children.append(
                {
                    "kind": "text",
                    "id": f"block-{block.line_number}",
                    "content": box_text,
                    "font": "monospace",
                }
            )

        default_open = any(
            keyword in section for keyword in ("Type", "Constant", "State")
        )
        elements.append(
            {
                "kind": "collapsing_header",
                "id": f"section-{section.replace(' ', '-').lower()}",
                "label": section,
                "default_open": default_open,
                "children": children,
            }
        )

    return elements


def _build_dashboard_tab(report: ProbReport, tex_path: Path) -> list[dict[str, Any]]:
    """Build Dashboard tab with metrics, checks table, and coverage table."""
    elements: list[dict[str, Any]] = []

    # Staleness warning
    if is_stale(tex_path):
        elements.append(
            {
                "kind": "text",
                "id": "stale-warning",
                "content": "⚠ Report may be stale — .tex is newer than report",
                "color": [1.0, 0.8, 0.0, 1.0],
            }
        )

    # Metric cards
    covered = sum(1 for op in report.operations if op.covered)
    total = len(report.operations)
    result_text = "PASS" if report.ok else "FAIL"
    elements.append(
        {
            "kind": "group",
            "id": "metrics",
            "layout": "columns",
            "children": [
                {
                    "kind": "text",
                    "id": "m-states",
                    "content": f"States: {report.states_analysed}",
                },
                {
                    "kind": "text",
                    "id": "m-trans",
                    "content": f"Transitions: {report.transitions_fired}",
                },
                {
                    "kind": "text",
                    "id": "m-coverage",
                    "content": f"Coverage: {covered}/{total} ops",
                },
                {
                    "kind": "text",
                    "id": "m-result",
                    "content": f"Result: {result_text}",
                },
            ],
        }
    )

    elements.append({"kind": "separator"})

    # Timestamp
    elements.append(
        {
            "kind": "text",
            "id": "timestamp",
            "content": (
                f"Last run: {report.timestamp}"
                f" | probcli {report.probcli_version}"
                f" | setsize={report.setsize}"
            ),
        }
    )

    elements.append({"kind": "separator"})

    # Checks table
    check_rows = [[c.name, c.status.value, c.detail] for c in report.checks]
    elements.append(
        {
            "kind": "table",
            "id": "checks",
            "columns": ["Check", "Status", "Details"],
            "rows": check_rows,
            "flags": ["borders", "row_bg"],
        }
    )

    # Operation coverage table
    if report.operations:
        elements.append({"kind": "separator"})
        op_rows = [
            [
                op.name,
                str(op.times_fired),
                "✓ covered" if op.covered else "✗ uncovered",
            ]
            for op in report.operations
        ]
        elements.append(
            {
                "kind": "table",
                "id": "ops-coverage",
                "columns": ["Operation", "Times Fired", "Status"],
                "rows": op_rows,
                "flags": ["borders", "row_bg", "resizable"],
            }
        )

    return elements


def _build_counter_example_tab(report: ProbReport) -> list[dict[str, Any]]:
    """Build Counter-Example tab with trace table and violation."""
    if report.counter_example is None:
        return []

    ce = report.counter_example
    elements: list[dict[str, Any]] = []

    elements.append(
        {
            "kind": "markdown",
            "id": "trace-header",
            "content": (
                "## Counter-Example Trace\n\n"
                "The model checker found a state sequence that violates "
                "an invariant or assertion."
            ),
        }
    )

    trace_rows = [
        [
            str(step.step_number),
            step.operation,
            ", ".join(f"{k}={v}" for k, v in step.state.items()) if step.state else "",
        ]
        for step in ce.steps
    ]
    elements.append(
        {
            "kind": "table",
            "id": "trace-steps",
            "columns": ["Step", "Operation", "State After"],
            "rows": trace_rows,
            "flags": ["borders", "row_bg"],
        }
    )

    if ce.violation:
        elements.append({"kind": "separator"})
        elements.append(
            {
                "kind": "markdown",
                "id": "trace-violation",
                "content": f"**Violated**: {ce.violation}",
            }
        )

    return elements


def build_z_spec_scene(
    tex_path: Path,
    spec: SpecModel,
    report: ProbReport | None = None,
) -> dict[str, Any]:
    """Pure builder: construct the full lux scene as a JSON-serializable dict."""
    tabs: list[dict[str, Any]] = []

    # Spec tab (always present)
    spec_elements = _build_spec_tab(spec)
    tabs.append({"label": "Spec", "children": spec_elements})

    # Dashboard tab (only if report exists)
    if report is not None:
        dashboard_elements = _build_dashboard_tab(report, tex_path)
        tabs.insert(0, {"label": "Dashboard", "children": dashboard_elements})

        # Counter-Example tab (only if violation found)
        if report.counter_example is not None:
            ce_elements = _build_counter_example_tab(report)
            tabs.insert(1, {"label": "Counter-Example", "children": ce_elements})

    title = f"{tex_path.name}"
    if report is not None:
        title += " — Model Check Results"

    return {
        "scene_id": "z-spec",
        "title": title,
        "elements": [
            {
                "kind": "tab_bar",
                "id": "z-spec-tabs",
                "tabs": tabs,
            }
        ],
    }


def show_applet(
    tex_path: Path,
    spec: SpecModel,
    report: ProbReport | None = None,
) -> dict[str, Any]:
    """Build scene and display via lux MCP. Returns status dict."""
    scene = build_z_spec_scene(tex_path, spec, report)

    try:
        from punt_lux.client import LuxClient  # pyright: ignore[reportMissingImports]
    except ImportError:
        return {"status": "scene_only", "scene": scene}

    try:
        with LuxClient(name="z-spec-applet") as client:
            client.show(  # type: ignore[call-arg]
                frame_id="z-spec",
                frame_title=scene["title"],
                elements=scene["elements"],
            )
        return {"status": "displayed", "scene_id": "z-spec"}
    except Exception:
        return {"status": "scene_only", "scene": scene}
