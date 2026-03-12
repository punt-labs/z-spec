"""Tests for punt_zspec.applet."""

from __future__ import annotations

from pathlib import Path

from punt_zspec.applet import build_z_spec_scene
from punt_zspec.types import (
    BlockKind,
    CheckResult,
    CheckStatus,
    CounterExample,
    OperationCoverage,
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


def test_build_spec_only_scene() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec)

    assert scene["scene_id"] == "z-spec"
    assert "test.tex" in scene["title"]
    assert "Model Check" not in scene["title"]

    # Should have tab_bar with one tab (Spec only)
    tab_bar = scene["elements"][0]
    assert tab_bar["kind"] == "tab_bar"
    assert len(tab_bar["tabs"]) == 1
    assert tab_bar["tabs"][0]["label"] == "Spec"


def test_build_scene_with_report() -> None:
    spec = _make_spec()
    report = _make_report()
    scene = build_z_spec_scene(Path("test.tex"), spec, report)

    assert "Model Check Results" in scene["title"]

    tab_bar = scene["elements"][0]
    tab_labels = [t["label"] for t in tab_bar["tabs"]]
    assert tab_labels == ["Dashboard", "Spec"]


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

    tab_bar = scene["elements"][0]
    tab_labels = [t["label"] for t in tab_bar["tabs"]]
    assert tab_labels == ["Dashboard", "Counter-Example", "Spec"]

    # Counter-Example tab has trace table
    ce_tab = tab_bar["tabs"][1]
    table = next(e for e in ce_tab["children"] if e.get("kind") == "table")
    assert table["rows"][0][1] == "INITIALISATION"
    assert table["rows"][1][1] == "Increment"


def test_spec_tab_has_collapsing_headers() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec)

    tab_bar = scene["elements"][0]
    spec_tab = tab_bar["tabs"][0]
    headers = [e for e in spec_tab["children"] if e["kind"] == "collapsing_header"]

    assert len(headers) == 3  # Basic Types, State, Operations
    # Types and State should be default open
    types_header = next(h for h in headers if h["label"] == "Basic Types")
    state_header = next(h for h in headers if h["label"] == "State")
    ops_header = next(h for h in headers if h["label"] == "Operations")
    assert types_header["default_open"] is True
    assert state_header["default_open"] is True
    assert ops_header["default_open"] is False


def test_spec_tab_renders_schema_boxes() -> None:
    spec = _make_spec()
    scene = build_z_spec_scene(Path("test.tex"), spec)

    tab_bar = scene["elements"][0]
    spec_tab = tab_bar["tabs"][0]
    # Find the State section
    state_header = next(
        e
        for e in spec_tab["children"]
        if e["kind"] == "collapsing_header" and e["label"] == "State"
    )

    text_block = state_header["children"][0]
    assert text_block["kind"] == "text"
    assert "┌─ State" in text_block["content"]
    assert "x : ℕ" in text_block["content"]
    assert "x ≤ 10" in text_block["content"]


def test_dashboard_has_metrics_and_checks() -> None:
    spec = _make_spec()
    report = _make_report()
    scene = build_z_spec_scene(Path("test.tex"), spec, report)

    tab_bar = scene["elements"][0]
    dashboard = tab_bar["tabs"][0]
    assert dashboard["label"] == "Dashboard"

    # Find metrics group
    metrics = next(e for e in dashboard["children"] if e.get("id") == "metrics")
    assert metrics["layout"] == "columns"
    metric_texts = [c["content"] for c in metrics["children"]]
    assert any("42" in t for t in metric_texts)  # states
    assert any("150" in t for t in metric_texts)  # transitions

    # Find checks table
    checks_table = next(e for e in dashboard["children"] if e.get("id") == "checks")
    assert len(checks_table["rows"]) == 5


def test_show_applet_without_lux() -> None:
    """show_applet gracefully degrades when punt-lux not installed."""
    from punt_zspec.applet import show_applet

    spec = _make_spec()
    result = show_applet(Path("test.tex"), spec)
    # Should return scene_only (since punt-lux isn't in test deps)
    assert result["status"] in ("scene_only", "displayed")
    if result["status"] == "scene_only":
        assert "scene" in result
