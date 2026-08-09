"""Lux applet: builds a Z spec's tabbed lux scene."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Self, final

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
from punt_lux.protocol.elements import Tab
from punt_lux.protocol.elements.table_flags import TableFlags

from punt_zspec.parser import render_schema_box
from punt_zspec.report import is_stale
from punt_zspec.types import (
    AuditReport,
    FuzzResult,
    PartitionReport,
    ProbReport,
    SpecModel,
    SpecReports,
)

# Substrings that trigger default-open for collapsing headers.
_DEFAULT_OPEN_KEYWORDS = ("Type", "Constant", "State")


@final
class _SpecSceneBuilder:
    """Build a Z spec's tabbed lux scene, namespacing every element id.

    Holds the spec, its reports, the source path, and an id prefix as state so
    each tab-building method reads shared context rather than threading it. The
    prefix keeps element ids unique when several spec scenes are embedded in one
    scene (the browser) — the 0.21 Hub rejects a tree with a repeated element id.
    """

    _tex_path: Path
    _spec: SpecModel
    _reports: SpecReports
    _prefix: str
    __slots__ = ("_prefix", "_reports", "_spec", "_tex_path")

    def __new__(
        cls, tex_path: Path, spec: SpecModel, reports: SpecReports, id_prefix: str
    ) -> Self:
        self = super().__new__(cls)
        self._tex_path = tex_path
        self._spec = spec
        self._reports = reports
        self._prefix = id_prefix
        return self

    def build(self) -> TabBarElement:
        """Assemble the tab bar: Spec plus a tab per report that is present."""
        p = self._prefix
        tabs: list[Tab] = [Tab(f"{p}spec", "Spec", tuple(self._spec_tab()))]

        fuzz = self._reports.fuzz
        if fuzz is not None:
            tabs.append(Tab(f"{p}fuzz", "Fuzz", tuple(self._fuzz_tab(fuzz))))

        report = self._reports.report
        if report is not None:
            tabs.append(Tab(f"{p}prob", "ProB", tuple(self._prob_tab(report))))
            if report.counter_example is not None:
                ce = self._counter_example_tab(report)
                tabs.append(Tab(f"{p}counter-example", "Counter-Example", tuple(ce)))

        partition = self._reports.partition
        if partition is not None:
            part = self._partition_tab(partition)
            tabs.append(Tab(f"{p}partition", "Partition", tuple(part)))

        audit = self._reports.audit
        if audit is not None:
            tabs.append(Tab(f"{p}audit", "Audit", tuple(self._audit_tab(audit))))

        return TabBarElement(id=f"{p}z-spec-tabs", tabs=tabs)

    def _spec_tab(self) -> list[Element]:
        """Schemas grouped by section with collapsing headers."""
        p = self._prefix
        elements: list[Element] = []
        by_section = self._spec.blocks_by_section()

        for section in self._spec.sections:
            blocks = by_section.get(section, [])
            if not blocks:
                continue

            children: list[Element] = [
                TextElement(
                    id=f"{p}block-{block.line_number}",
                    content=render_schema_box(block),
                    style="code",
                )
                for block in blocks
            ]
            default_open = any(k in section for k in _DEFAULT_OPEN_KEYWORDS)
            elements.append(
                CollapsingHeaderElement(
                    id=f"{p}section-{section.replace(' ', '-').lower()}",
                    label=section,
                    open=default_open,
                    children=children,
                )
            )

        return elements

    def _fuzz_tab(self, fuzz: FuzzResult) -> list[Element]:
        """Pass/fail status and, on failure, the error table."""
        p = self._prefix
        result_text = "PASS — no type errors" if fuzz.ok else "FAIL — type errors found"
        elements: list[Element] = [
            TextElement(id=f"{p}fuzz-result", content=f"Result: {result_text}")
        ]

        if fuzz.errors:
            elements.append(SeparatorElement())
            error_rows = [[str(e.line), str(e.column), e.message] for e in fuzz.errors]
            elements.append(
                TableElement(
                    id=f"{p}fuzz-errors",
                    columns=["Line", "Column", "Message"],
                    rows=error_rows,
                    flags=TableFlags(),
                )
            )

        return elements

    def _prob_tab(self, report: ProbReport) -> list[Element]:
        """Metrics cards, timestamp, checks table, and coverage table."""
        p = self._prefix
        elements: list[Element] = []

        if is_stale(self._tex_path):
            elements.append(
                TextElement(
                    id=f"{p}stale-warning",
                    content="⚠ Report may be stale — .tex is newer than report",
                )
            )

        # No operations means no counts to show, not zero of them. Rendering
        # "0/0 ops" states a measurement that was not taken; the checks table
        # below already carries the coverage verdict and its reason, and a card
        # that recomputes what it was handed is how this defect was written the
        # first time.
        covered = sum(1 for op in report.operations if op.covered)
        coverage_text = (
            f"Coverage: {covered}/{len(report.operations)} ops"
            if report.operations
            else "Coverage: not measured"
        )
        result_text = "PASS" if report.ok else "FAIL"
        elements.append(
            GroupElement(
                id=f"{p}metrics",
                layout="columns",
                children=[
                    TextElement(
                        id=f"{p}m-states", content=f"States: {report.states_analysed}"
                    ),
                    TextElement(
                        id=f"{p}m-trans",
                        content=f"Transitions: {report.transitions_fired}",
                    ),
                    TextElement(id=f"{p}m-coverage", content=coverage_text),
                    TextElement(id=f"{p}m-result", content=f"Result: {result_text}"),
                ],
            )
        )

        elements.append(SeparatorElement())
        elements.append(
            TextElement(
                id=f"{p}timestamp",
                content=(
                    f"Last run: {report.timestamp}"
                    f" | probcli {report.probcli_version}"
                    f" | setsize={report.setsize}"
                ),
            )
        )

        elements.append(SeparatorElement())
        check_rows = [[c.name, c.status.value, c.detail] for c in report.checks]
        elements.append(
            TableElement(
                id=f"{p}checks",
                columns=["Check", "Status", "Details"],
                rows=check_rows,
                flags=TableFlags(),
            )
        )

        if not report.operations:
            elements.append(SeparatorElement())
            elements.append(
                TextElement(
                    id=f"{p}ops-absent",
                    content="No operation census in this report — see coverage above.",
                )
            )
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
                    id=f"{p}ops-coverage",
                    columns=["Operation", "Times Fired", "Status"],
                    rows=op_rows,
                    flags=TableFlags(resizable=True),
                )
            )

        return elements

    def _counter_example_tab(self, report: ProbReport) -> list[Element]:
        """Trace table and the violated predicate."""
        p = self._prefix
        if report.counter_example is None:
            return []

        ce = report.counter_example
        elements: list[Element] = [
            MarkdownElement(
                id=f"{p}trace-header",
                content=(
                    "## Counter-Example Trace\n\n"
                    "The model checker found a state sequence that violates "
                    "an invariant or assertion."
                ),
            )
        ]

        trace_rows = [
            [
                str(step.step_number),
                step.operation,
                ", ".join(f"{k}={v}" for k, v in step.state.items())
                if step.state
                else "",
            ]
            for step in ce.steps
        ]
        elements.append(
            TableElement(
                id=f"{p}trace-steps",
                columns=["Step", "Operation", "State After"],
                rows=trace_rows,
                flags=TableFlags(),
            )
        )

        if ce.violation:
            elements.append(SeparatorElement())
            elements.append(
                MarkdownElement(
                    id=f"{p}trace-violation",
                    content=f"**Violated**: {ce.violation}",
                )
            )

        return elements

    def _partition_tab(self, report: PartitionReport) -> list[Element]:
        """Summary metrics and a per-operation partition table."""
        p = self._prefix
        elements: list[Element] = [
            GroupElement(
                id=f"{p}part-metrics",
                layout="columns",
                children=[
                    TextElement(
                        id=f"{p}part-ops",
                        content=f"Operations: {len(report.operations)}",
                    ),
                    TextElement(
                        id=f"{p}part-total",
                        content=f"Partitions: {report.total_partitions}",
                    ),
                    TextElement(
                        id=f"{p}part-accepted",
                        content=f"Accepted: {report.total_accepted}",
                    ),
                    TextElement(
                        id=f"{p}part-rejected",
                        content=f"Rejected: {report.total_rejected}",
                    ),
                ],
            ),
            SeparatorElement(),
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
        for op in report.operations:
            summary = op.summary
            rows = [
                [
                    str(part.id),
                    part.class_name,
                    str(part.branch) if part.branch is not None else "-",
                    part.status.value,
                    self._format_dict(part.inputs),
                    self._format_dict(part.pre_state),
                    self._format_dict(part.post_state)
                    if part.post_state
                    else "(no change)",
                    part.notes,
                ]
                for part in op.partitions
            ]
            table = TableElement(
                id=f"{p}part-{op.name}",
                columns=part_cols,
                rows=rows,
                flags=TableFlags(resizable=True),
            )
            a, r, pr = summary["accepted"], summary["rejected"], summary["pruned"]
            elements.append(
                CollapsingHeaderElement(
                    id=f"{p}part-section-{op.name}",
                    label=f"{op.name} ({a}A / {r}R / {pr}P)",
                    open=True,
                    children=[table],
                )
            )

        return elements

    def _audit_tab(self, report: AuditReport) -> list[Element]:
        """Coverage summary, per-category breakdown, and constraint tables."""
        p = self._prefix
        elements: list[Element] = [
            GroupElement(
                id=f"{p}audit-metrics",
                layout="columns",
                children=[
                    TextElement(
                        id=f"{p}audit-coverage",
                        content=(
                            f"Coverage: {report.covered_count}"
                            f"/{report.total}"
                            f" ({report.percentage}%)"
                        ),
                    ),
                    TextElement(
                        id=f"{p}audit-tests",
                        content=f"Test dir: {report.test_directory}",
                    ),
                ],
            )
        ]

        by_cat = report.by_category
        if by_cat:
            cat_rows = [
                [cat, str(vals["covered"]), str(vals["total"])]
                for cat, vals in by_cat.items()
            ]
            elements.append(
                TableElement(
                    id=f"{p}audit-categories",
                    columns=["Category", "Covered", "Total"],
                    rows=cat_rows,
                    flags=TableFlags(),
                )
            )

        elements.append(SeparatorElement())

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
                    id=f"{p}audit-covered",
                    label=f"Covered Constraints ({len(report.constraints)})",
                    open=False,
                    children=[
                        TableElement(
                            id=f"{p}audit-covered-table",
                            columns=[
                                "Constraint",
                                "Category",
                                "Source",
                                "Covered By",
                                "Confidence",
                            ],
                            rows=covered_rows,
                            flags=TableFlags(resizable=True),
                        )
                    ],
                )
            )

        if report.uncovered:
            uncovered_rows = [
                [u.text, u.category, u.source, u.suggestion, u.test_pattern]
                for u in report.uncovered
            ]
            elements.append(
                CollapsingHeaderElement(
                    id=f"{p}audit-uncovered",
                    label=f"Uncovered Constraints ({len(report.uncovered)})",
                    open=True,
                    children=[
                        TableElement(
                            id=f"{p}audit-uncovered-table",
                            columns=[
                                "Constraint",
                                "Category",
                                "Source",
                                "Suggestion",
                                "Test Pattern",
                            ],
                            rows=uncovered_rows,
                            flags=TableFlags(resizable=True),
                        )
                    ],
                )
            )

        return elements

    @staticmethod
    def _format_dict(d: dict[str, Any]) -> str:
        """Format a dict as compact key=value pairs."""
        if not d:
            return ""
        return ", ".join(f"{k}={v}" for k, v in d.items())


def build_z_spec_scene(
    tex_path: Path,
    spec: SpecModel,
    report: ProbReport | None = None,
    fuzz: FuzzResult | None = None,
    partition: PartitionReport | None = None,
    audit: AuditReport | None = None,
    id_prefix: str = "",
) -> TabBarElement:
    """Construct the full lux scene as a typed TabBarElement.

    ``id_prefix`` namespaces every element id so a caller embedding several spec
    scenes in one scene (the browser) keeps ids unique — the 0.21 Hub rejects a
    tree with a repeated element id.
    """
    reports = SpecReports(report=report, fuzz=fuzz, partition=partition, audit=audit)
    return _SpecSceneBuilder(tex_path, spec, reports, id_prefix).build()
