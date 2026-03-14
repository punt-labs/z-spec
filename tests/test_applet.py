"""Tests for punt_zspec.applet."""

from __future__ import annotations

from pathlib import Path

from punt_lux.protocol import (
    CollapsingHeaderElement,
    GroupElement,
    MarkdownElement,
    TabBarElement,
    TableElement,
    TextElement,
)

from punt_zspec.applet import build_z_spec_scene
from punt_zspec.types import (
    AuditConfidence,
    AuditConstraint,
    AuditReport,
    AuditSuggestion,
    BlockKind,
    CheckResult,
    CheckStatus,
    CounterExample,
    FuzzError,
    FuzzResult,
    OperationCoverage,
    OperationPartitions,
    Partition,
    PartitionReport,
    PartitionStatus,
    ProbReport,
    SpecModel,
    TraceStep,
    ZBlock,
)


def _make_spec() -> SpecModel:
    return SpecModel(
        title="Test Spec",
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


def _make_report() -> ProbReport:
    return ProbReport(
        timestamp="2026-03-12T00:00:00Z",
        probcli_version="1.13.1",
        setsize=2,
        checks=[
            CheckResult(name="init", status=CheckStatus.passed, detail="OK"),
            CheckResult(
                name="animate", status=CheckStatus.passed, detail="all ops covered"
            ),
            CheckResult(
                name="cbc_assertions",
                status=CheckStatus.skipped,
                detail="no assertions",
            ),
            CheckResult(
                name="cbc_deadlock", status=CheckStatus.passed, detail="deadlock-free"
            ),
            CheckResult(
                name="model_check", status=CheckStatus.passed, detail="42 states"
            ),
        ],
        operations=[
            OperationCoverage(name="Increment", times_fired=10, covered=True),
        ],
        counter_example=None,
        states_analysed=42,
        transitions_fired=150,
    )


def _make_fuzz_ok() -> FuzzResult:
    return FuzzResult(ok=True)


def _make_fuzz_errors() -> FuzzResult:
    return FuzzResult(
        ok=False,
        errors=[
            FuzzError(line=10, column=5, message="undeclared identifier"),
            FuzzError(line=20, column=1, message="type mismatch"),
        ],
    )


def _make_partition() -> PartitionReport:
    return PartitionReport(
        specification="test.tex",
        timestamp="2026-03-12T00:00:00Z",
        operations=[
            OperationPartitions(
                name="Increment",
                kind="delta",
                inputs=[{"name": "n", "type": "nat", "constraints": ["n <= 10"]}],
                state_vars=["x"],
                branches=[{"id": 1, "description": "Normal", "condition": "x < 10"}],
                partitions=[
                    Partition(
                        id=1,
                        class_name="happy-path",
                        branch=1,
                        status=PartitionStatus.accepted,
                        inputs={"n": 1},
                        pre_state={"x": 5},
                        post_state={"x": 6},
                        notes="Normal case",
                    ),
                    Partition(
                        id=2,
                        class_name="boundary: max",
                        branch=1,
                        status=PartitionStatus.accepted,
                        inputs={"n": 1},
                        pre_state={"x": 9},
                        post_state={"x": 10},
                        notes="At upper bound",
                    ),
                    Partition(
                        id=3,
                        class_name="rejected",
                        branch=None,
                        status=PartitionStatus.rejected,
                        inputs={"n": 1},
                        pre_state={"x": 10},
                        post_state=None,
                        notes="Precondition fails",
                    ),
                ],
            )
        ],
    )


def _make_audit() -> AuditReport:
    return AuditReport(
        specification="test.tex",
        test_directory="tests/",
        timestamp="2026-03-12T00:00:00Z",
        constraints=[
            AuditConstraint(
                text="x <= 10",
                category="invariant",
                source="State",
                covered_by="test_state.py:15",
                confidence=AuditConfidence.high,
            ),
            AuditConstraint(
                text="x >= 0",
                category="invariant",
                source="State",
                covered_by="test_state.py:20",
                confidence=AuditConfidence.medium,
            ),
        ],
        uncovered=[
            AuditSuggestion(
                text="x' = x + 1",
                category="effect",
                source="Increment",
                suggestion="Test that Increment increases x by 1",
                test_pattern="assert state.x == old_x + 1",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Spec tab tests
# ---------------------------------------------------------------------------


def test_build_spec_only_scene() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec)

    assert isinstance(scene, TabBarElement)
    assert scene.id == "z-spec-tabs"

    # Should have one tab (Spec only)
    assert len(scene.tabs) == 1
    assert scene.tabs[0]["label"] == "Spec"


def test_spec_tab_has_collapsing_headers() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec)

    spec_children = scene.tabs[0]["children"]
    headers = [e for e in spec_children if isinstance(e, CollapsingHeaderElement)]

    assert len(headers) == 3  # Basic Types, State, Operations
    types_header = next(h for h in headers if h.label == "Basic Types")
    state_header = next(h for h in headers if h.label == "State")
    ops_header = next(h for h in headers if h.label == "Operations")
    assert types_header.default_open is True
    assert state_header.default_open is True
    assert ops_header.default_open is False


def test_spec_tab_renders_schema_boxes() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec)

    spec_children = scene.tabs[0]["children"]
    state_header = next(
        e
        for e in spec_children
        if isinstance(e, CollapsingHeaderElement) and e.label == "State"
    )

    text_block = state_header.children[0]
    assert isinstance(text_block, TextElement)
    assert "┌─ State" in text_block.content
    assert "x : ℕ" in text_block.content
    assert "x ≤ 10" in text_block.content


# ---------------------------------------------------------------------------
# Fuzz tab tests
# ---------------------------------------------------------------------------


def test_fuzz_tab_pass() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec, fuzz=_make_fuzz_ok())

    tab_labels = [t["label"] for t in scene.tabs]
    assert "Fuzz" in tab_labels

    fuzz_children = scene.tabs[1]["children"]
    result_text = next(e for e in fuzz_children if isinstance(e, TextElement))
    assert "PASS" in result_text.content


def test_fuzz_tab_errors() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec, fuzz=_make_fuzz_errors())

    fuzz_children = scene.tabs[1]["children"]
    result_text = next(e for e in fuzz_children if isinstance(e, TextElement))
    assert "FAIL" in result_text.content

    error_table = next(e for e in fuzz_children if isinstance(e, TableElement))
    assert len(error_table.rows) == 2
    assert error_table.rows[0][2] == "undeclared identifier"


# ---------------------------------------------------------------------------
# ProB tab tests
# ---------------------------------------------------------------------------


def test_build_scene_with_report() -> None:
    spec = _make_spec()
    report = _make_report()
    scene = build_z_spec_scene(Path("test.tex"), spec, report)

    assert isinstance(scene, TabBarElement)
    tab_labels = [t["label"] for t in scene.tabs]
    assert tab_labels == ["Spec", "ProB"]


def test_build_scene_with_counter_example() -> None:
    spec = _make_spec()
    report = ProbReport(
        timestamp="2026-03-12T00:00:00Z",
        probcli_version="1.13.1",
        setsize=2,
        checks=[
            CheckResult(
                name="model_check", status=CheckStatus.failed, detail="violation"
            ),
        ],
        operations=[],
        counter_example=CounterExample(
            steps=[
                TraceStep(step_number=0, operation="INITIALISATION", state={"x": "0"}),
                TraceStep(step_number=1, operation="Increment", state={"x": "11"}),
            ],
            violation="x ≤ 10",
        ),
        states_analysed=5,
        transitions_fired=8,
    )
    scene = build_z_spec_scene(Path("test.tex"), spec, report)

    tab_labels = [t["label"] for t in scene.tabs]
    assert tab_labels == ["Spec", "ProB", "Counter-Example"]

    ce_children = scene.tabs[2]["children"]
    table = next(e for e in ce_children if isinstance(e, TableElement))
    assert table.rows[0][1] == "INITIALISATION"
    assert table.rows[1][1] == "Increment"


def test_prob_tab_has_metrics_and_checks() -> None:
    spec = _make_spec()
    report = _make_report()
    scene = build_z_spec_scene(Path("test.tex"), spec, report)

    prob_children = scene.tabs[1]["children"]
    assert scene.tabs[1]["label"] == "ProB"

    metrics = next(e for e in prob_children if isinstance(e, GroupElement))
    assert metrics.layout == "columns"
    metric_texts = [c.content for c in metrics.children if isinstance(c, TextElement)]
    assert any("42" in t for t in metric_texts)
    assert any("150" in t for t in metric_texts)

    checks_table = next(
        e for e in prob_children if isinstance(e, TableElement) and e.id == "checks"
    )
    assert len(checks_table.rows) == 5


def test_counter_example_tab_has_violation_markdown() -> None:
    spec = _make_spec()
    report = ProbReport(
        timestamp="2026-03-12T00:00:00Z",
        probcli_version="1.13.1",
        setsize=2,
        checks=[
            CheckResult(
                name="model_check", status=CheckStatus.failed, detail="violation"
            ),
        ],
        operations=[],
        counter_example=CounterExample(
            steps=[
                TraceStep(step_number=0, operation="INITIALISATION", state={"x": "0"}),
            ],
            violation="x ≤ 10",
        ),
        states_analysed=5,
        transitions_fired=8,
    )
    scene = build_z_spec_scene(Path("test.tex"), spec, report)

    ce_children = scene.tabs[2]["children"]
    violation = next(
        e
        for e in ce_children
        if isinstance(e, MarkdownElement) and "Violated" in e.content
    )
    assert "x ≤ 10" in violation.content


# ---------------------------------------------------------------------------
# Partition tab tests
# ---------------------------------------------------------------------------


def test_partition_tab_present() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec, partition=_make_partition())

    tab_labels = [t["label"] for t in scene.tabs]
    assert "Partition" in tab_labels


def test_partition_tab_has_metrics() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec, partition=_make_partition())

    part_tab = next(t for t in scene.tabs if t["label"] == "Partition")
    metrics = next(e for e in part_tab["children"] if isinstance(e, GroupElement))
    metric_texts = [c.content for c in metrics.children if isinstance(c, TextElement)]
    assert any("3" in t for t in metric_texts)  # total partitions
    assert any("2" in t for t in metric_texts)  # accepted


def test_partition_tab_has_operation_table() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec, partition=_make_partition())

    part_tab = next(t for t in scene.tabs if t["label"] == "Partition")
    header = next(
        e for e in part_tab["children"] if isinstance(e, CollapsingHeaderElement)
    )
    assert "Increment" in header.label
    assert header.default_open is True

    table = header.children[0]
    assert isinstance(table, TableElement)
    assert len(table.rows) == 3
    assert table.rows[0][1] == "happy-path"
    assert table.rows[2][3] == "rejected"


# ---------------------------------------------------------------------------
# Audit tab tests
# ---------------------------------------------------------------------------


def test_audit_tab_present() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec, audit=_make_audit())

    tab_labels = [t["label"] for t in scene.tabs]
    assert "Audit" in tab_labels


def test_audit_tab_has_coverage_metrics() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec, audit=_make_audit())

    audit_tab = next(t for t in scene.tabs if t["label"] == "Audit")
    metrics = next(e for e in audit_tab["children"] if isinstance(e, GroupElement))
    metric_texts = [c.content for c in metrics.children if isinstance(c, TextElement)]
    assert any("2/3" in t for t in metric_texts)  # covered/total
    assert any("67%" in t for t in metric_texts)  # percentage


def test_audit_tab_has_uncovered_section() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec, audit=_make_audit())

    audit_tab = next(t for t in scene.tabs if t["label"] == "Audit")
    uncovered_header = next(
        e
        for e in audit_tab["children"]
        if isinstance(e, CollapsingHeaderElement) and "Uncovered" in e.label
    )
    assert uncovered_header.default_open is True
    table = uncovered_header.children[0]
    assert isinstance(table, TableElement)
    assert len(table.rows) == 1
    assert "x' = x + 1" in table.rows[0][0]


# ---------------------------------------------------------------------------
# All tabs together
# ---------------------------------------------------------------------------


def test_all_tabs_present() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(
        Path("test.tex"),
        spec,
        report=_make_report(),
        fuzz=_make_fuzz_ok(),
        partition=_make_partition(),
        audit=_make_audit(),
    )

    tab_labels = [t["label"] for t in scene.tabs]
    assert tab_labels == ["Spec", "Fuzz", "ProB", "Partition", "Audit"]
