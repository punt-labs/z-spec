"""Lux applet: builds typed element tree for Z spec display."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from punt_lux.protocol import (
    CollapsingHeaderElement,
    Element,
    GroupElement,
    MarkdownElement,
    SeparatorElement,
    TabBarElement,
    TableElement,
    TextElement,
)

from punt_zspec.parser import render_schema_box
from punt_zspec.report import is_stale
from punt_zspec.types import (
    AuditReport,
    FuzzResult,
    PartitionReport,
    ProbReport,
    SpecModel,
)

# Substrings that trigger default-open for collapsing headers.
_DEFAULT_OPEN_KEYWORDS = ("Type", "Constant", "State")


# ---------------------------------------------------------------------------
# Spec tab
# ---------------------------------------------------------------------------


def _build_spec_tab(spec: SpecModel) -> list[Element]:
    """Build Spec tab elements: schemas grouped by section with collapsing headers."""
    elements: list[Element] = []
    by_section = spec.blocks_by_section()

    for section in spec.sections:
        blocks = by_section.get(section, [])
        if not blocks:
            continue

        children: list[Element] = []
        for block in blocks:
            box_text = render_schema_box(block)
            children.append(
                TextElement(
                    id=f"block-{block.line_number}",
                    content=box_text,
                    style="code",
                )
            )

        default_open = any(keyword in section for keyword in _DEFAULT_OPEN_KEYWORDS)
        elements.append(
            CollapsingHeaderElement(
                id=f"section-{section.replace(' ', '-').lower()}",
                label=section,
                default_open=default_open,
                children=children,
            )
        )

    return elements


# ---------------------------------------------------------------------------
# Fuzz tab
# ---------------------------------------------------------------------------


def _build_fuzz_tab(fuzz: FuzzResult) -> list[Element]:
    """Build Fuzz tab with pass/fail status and error table."""
    elements: list[Element] = []

    result_text = "PASS — no type errors" if fuzz.ok else "FAIL — type errors found"
    elements.append(TextElement(id="fuzz-result", content=f"Result: {result_text}"))

    if fuzz.errors:
        elements.append(SeparatorElement())
        error_rows = [[str(e.line), str(e.column), e.message] for e in fuzz.errors]
        elements.append(
            TableElement(
                id="fuzz-errors",
                columns=["Line", "Column", "Message"],
                rows=error_rows,
                flags=["borders", "row_bg"],
            )
        )

    return elements


# ---------------------------------------------------------------------------
# ProB tab
# ---------------------------------------------------------------------------


def _build_prob_tab(report: ProbReport, tex_path: Path) -> list[Element]:
    """Build ProB tab with metrics, checks table, and coverage table."""
    elements: list[Element] = []

    # Staleness warning
    if is_stale(tex_path):
        elements.append(
            TextElement(
                id="stale-warning",
                content="⚠ Report may be stale — .tex is newer than report",
            )
        )

    # Metric cards
    covered = sum(1 for op in report.operations if op.covered)
    total = len(report.operations)
    result_text = "PASS" if report.ok else "FAIL"
    elements.append(
        GroupElement(
            id="metrics",
            layout="columns",
            children=[
                TextElement(
                    id="m-states",
                    content=f"States: {report.states_analysed}",
                ),
                TextElement(
                    id="m-trans",
                    content=f"Transitions: {report.transitions_fired}",
                ),
                TextElement(
                    id="m-coverage",
                    content=f"Coverage: {covered}/{total} ops",
                ),
                TextElement(
                    id="m-result",
                    content=f"Result: {result_text}",
                ),
            ],
        )
    )

    elements.append(SeparatorElement())

    # Timestamp
    elements.append(
        TextElement(
            id="timestamp",
            content=(
                f"Last run: {report.timestamp}"
                f" | probcli {report.probcli_version}"
                f" | setsize={report.setsize}"
            ),
        )
    )

    elements.append(SeparatorElement())

    # Checks table
    check_rows = [[c.name, c.status.value, c.detail] for c in report.checks]
    elements.append(
        TableElement(
            id="checks",
            columns=["Check", "Status", "Details"],
            rows=check_rows,
            flags=["borders", "row_bg"],
        )
    )

    # Operation coverage table
    if report.operations:
        elements.append(SeparatorElement())
        op_rows = [
            [
                op.name,
                str(op.times_fired),
                "✓ covered" if op.covered else "✗ uncovered",
            ]
            for op in report.operations
        ]
        elements.append(
            TableElement(
                id="ops-coverage",
                columns=["Operation", "Times Fired", "Status"],
                rows=op_rows,
                flags=["borders", "row_bg", "resizable"],
            )
        )

    return elements


# ---------------------------------------------------------------------------
# Counter-Example tab
# ---------------------------------------------------------------------------


def _build_counter_example_tab(report: ProbReport) -> list[Element]:
    """Build Counter-Example tab with trace table and violation."""
    if report.counter_example is None:
        return []

    ce = report.counter_example
    elements: list[Element] = []

    elements.append(
        MarkdownElement(
            id="trace-header",
            content=(
                "## Counter-Example Trace\n\n"
                "The model checker found a state sequence that violates "
                "an invariant or assertion."
            ),
        )
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
        TableElement(
            id="trace-steps",
            columns=["Step", "Operation", "State After"],
            rows=trace_rows,
            flags=["borders", "row_bg"],
        )
    )

    if ce.violation:
        elements.append(SeparatorElement())
        elements.append(
            MarkdownElement(
                id="trace-violation",
                content=f"**Violated**: {ce.violation}",
            )
        )

    return elements


# ---------------------------------------------------------------------------
# Partition tab
# ---------------------------------------------------------------------------


def _build_partition_tab(report: PartitionReport) -> list[Element]:
    """Build Partition tab with per-operation partition tables."""
    elements: list[Element] = []

    # Summary metrics
    elements.append(
        GroupElement(
            id="part-metrics",
            layout="columns",
            children=[
                TextElement(
                    id="part-ops",
                    content=f"Operations: {len(report.operations)}",
                ),
                TextElement(
                    id="part-total",
                    content=f"Partitions: {report.total_partitions}",
                ),
                TextElement(
                    id="part-accepted",
                    content=f"Accepted: {report.total_accepted}",
                ),
                TextElement(
                    id="part-rejected",
                    content=f"Rejected: {report.total_rejected}",
                ),
            ],
        )
    )

    elements.append(SeparatorElement())

    # Per-operation collapsing sections
    for op in report.operations:
        summary = op.summary
        rows = [
            [
                str(p.id),
                p.class_name,
                str(p.branch) if p.branch is not None else "-",
                p.status.value,
                _format_dict(p.inputs),
                _format_dict(p.pre_state),
                _format_dict(p.post_state) if p.post_state else "(no change)",
                p.notes,
            ]
            for p in op.partitions
        ]
        part_cols = [
            "#",
            "Class",
            "Branch",
            "Status",
            "Inputs",
            "Pre-state",
            "Post-state",
            "Notes",
        ]
        table = TableElement(
            id=f"part-{op.name}",
            columns=part_cols,
            rows=rows,
            flags=["borders", "row_bg", "resizable"],
        )
        a, r, p = summary["accepted"], summary["rejected"], summary["pruned"]
        label = f"{op.name} ({a}A / {r}R / {p}P)"
        elements.append(
            CollapsingHeaderElement(
                id=f"part-section-{op.name}",
                label=label,
                default_open=True,
                children=[table],
            )
        )

    return elements


def _format_dict(d: dict[str, Any]) -> str:
    """Format a dict as compact key=value pairs."""
    if not d:
        return ""
    return ", ".join(f"{k}={v}" for k, v in d.items())


# ---------------------------------------------------------------------------
# Audit tab
# ---------------------------------------------------------------------------


def _build_audit_tab(report: AuditReport) -> list[Element]:
    """Build Audit tab with coverage summary and constraint tables."""
    elements: list[Element] = []

    # Summary metrics
    elements.append(
        GroupElement(
            id="audit-metrics",
            layout="columns",
            children=[
                TextElement(
                    id="audit-coverage",
                    content=(
                        f"Coverage: {report.covered_count}"
                        f"/{report.total}"
                        f" ({report.percentage}%)"
                    ),
                ),
                TextElement(
                    id="audit-tests",
                    content=f"Test dir: {report.test_directory}",
                ),
            ],
        )
    )

    # Per-category breakdown
    by_cat = report.by_category
    if by_cat:
        cat_rows = [
            [cat, str(vals["covered"]), str(vals["total"])]
            for cat, vals in by_cat.items()
        ]
        elements.append(
            TableElement(
                id="audit-categories",
                columns=["Category", "Covered", "Total"],
                rows=cat_rows,
                flags=["borders", "row_bg"],
            )
        )

    elements.append(SeparatorElement())

    # Covered constraints
    if report.constraints:
        covered_rows = [
            [
                c.text,
                c.category,
                c.source,
                c.covered_by or "",
                c.confidence.value if c.confidence else "",
            ]
            for c in report.constraints
        ]
        elements.append(
            CollapsingHeaderElement(
                id="audit-covered",
                label=f"Covered Constraints ({len(report.constraints)})",
                default_open=False,
                children=[
                    TableElement(
                        id="audit-covered-table",
                        columns=[
                            "Constraint",
                            "Category",
                            "Source",
                            "Covered By",
                            "Confidence",
                        ],
                        rows=covered_rows,
                        flags=["borders", "row_bg", "resizable"],
                    )
                ],
            )
        )

    # Uncovered constraints (more important — default open)
    if report.uncovered:
        uncovered_rows = [
            [u.text, u.category, u.source, u.suggestion, u.test_pattern]
            for u in report.uncovered
        ]
        elements.append(
            CollapsingHeaderElement(
                id="audit-uncovered",
                label=f"Uncovered Constraints ({len(report.uncovered)})",
                default_open=True,
                children=[
                    TableElement(
                        id="audit-uncovered-table",
                        columns=[
                            "Constraint",
                            "Category",
                            "Source",
                            "Suggestion",
                            "Test Pattern",
                        ],
                        rows=uncovered_rows,
                        flags=["borders", "row_bg", "resizable"],
                    )
                ],
            )
        )

    return elements


# ---------------------------------------------------------------------------
# Scene builder
# ---------------------------------------------------------------------------


def build_z_spec_scene(
    tex_path: Path,
    spec: SpecModel,
    report: ProbReport | None = None,
    fuzz: FuzzResult | None = None,
    partition: PartitionReport | None = None,
    audit: AuditReport | None = None,
) -> TabBarElement:
    """Pure builder: construct the full lux scene as a typed TabBarElement."""
    tabs: list[dict[str, Any]] = []

    # Spec tab (always first)
    spec_elements = _build_spec_tab(spec)
    tabs.append({"label": "Spec", "children": spec_elements})

    # Fuzz tab (if result exists)
    if fuzz is not None:
        fuzz_elements = _build_fuzz_tab(fuzz)
        tabs.append({"label": "Fuzz", "children": fuzz_elements})

    # ProB tab (if report exists)
    if report is not None:
        prob_elements = _build_prob_tab(report, tex_path)
        tabs.append({"label": "ProB", "children": prob_elements})

        # Counter-Example tab (only if violation found)
        if report.counter_example is not None:
            ce_elements = _build_counter_example_tab(report)
            tabs.append({"label": "Counter-Example", "children": ce_elements})

    # Partition tab (if report exists)
    if partition is not None:
        part_elements = _build_partition_tab(partition)
        tabs.append({"label": "Partition", "children": part_elements})

    # Audit tab (if report exists)
    if audit is not None:
        audit_elements = _build_audit_tab(audit)
        tabs.append({"label": "Audit", "children": audit_elements})

    return TabBarElement(id="z-spec-tabs", tabs=tabs)
