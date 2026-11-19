"""Consumer tests for z-spec's punt-observe diagnostics and usage telemetry.

The shared package owns redaction, rotation and storage and tests them
itself. These tests prove z-spec's side of the contract: each entry point
configures a private durable log, every capability call records one typed
usage event, the off switches stop capture without touching diagnostics, and
an exporter swap needs no change to z-spec's instrumentation.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import stat
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, final

import pytest
from opentelemetry.sdk.metrics.export import (
    MetricExporter,
    MetricExportResult,
    MetricsData,
)
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from punt_observe.telemetry import SchemaRegistry, TelemetryConfig
from typer.testing import CliRunner

from punt_zspec.__main__ import app
from punt_zspec.commands.doctor import DoctorReport
from punt_zspec.commands.registry import CAPABILITIES
from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.logging_config import DiagnosticLog
from punt_zspec.usage import SCHEMA_VERSION, Usage, schemas, signal_name

if TYPE_CHECKING:
    from collections.abc import Sequence

    from opentelemetry.sdk.trace import ReadableSpan

_SRC = Path(__file__).resolve().parents[1] / "src"
_TIMEOUT_S = 120


def _log(home: Path) -> Path:
    return home / ".punt-labs" / "z-spec" / "logs" / "z-spec.log"


def _db(home: Path) -> Path:
    return home / ".punt-labs" / "z-spec" / "telemetry.db"


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _env(home: Path, **extra: str) -> dict[str, str]:
    return {**os.environ, "HOME": str(home), **extra}


def _cli(home: Path, *args: str, **extra: str) -> subprocess.CompletedProcess[str]:
    """Run the real ``z-spec`` entry point in a child process."""
    return subprocess.run(
        [sys.executable, "-m", "punt_zspec", *args],
        capture_output=True,
        text=True,
        env=_env(home, **extra),
        timeout=_TIMEOUT_S,
        check=False,
    )


def _events(home: Path) -> list[tuple[str, dict[str, Any]]]:
    conn = sqlite3.connect(_db(home))
    try:
        rows = conn.execute("SELECT name, attributes FROM spans").fetchall()
    finally:
        conn.close()
    return [(str(name), json.loads(attrs)) for name, attrs in rows]


@pytest.fixture
def not_a_repo(tmp_path: Path) -> Path:
    """Return a directory outside any git repository: ``disable`` fails there."""
    path = tmp_path / "secret-project-name"
    path.mkdir()
    return path


def test_cli_entry_point_writes_private_durable_log(
    private_home: Path, not_a_repo: Path
) -> None:
    proc = _cli(private_home, "disable", str(not_a_repo))

    assert proc.returncode == 1
    log = _log(private_home)
    assert _mode(log.parent) == 0o700
    assert _mode(log) == 0o600
    text = log.read_text("utf-8")
    assert "Completed disable via cli: outcome=failed failure=not_a_repository" in text
    assert not_a_repo.name not in text
    assert "[INFO]" not in proc.stdout + proc.stderr


def test_cli_usage_event_carries_only_typed_attributes(
    private_home: Path, not_a_repo: Path
) -> None:
    _cli(private_home, "disable", str(not_a_repo))

    db = _db(private_home)
    assert _mode(db) == 0o600
    [(name, attrs)] = _events(private_home)
    assert name == "z-spec.cli.disable"
    assert attrs["outcome"] == "failed"
    assert attrs["failure"] == "not_a_repository"
    assert attrs["duration_ms"] >= 0
    assert not_a_repo.name.encode() not in db.read_bytes()


@pytest.mark.parametrize("switch", ["PUNT_TELEMETRY", "Z_SPEC_TELEMETRY"])
def test_off_switch_stops_capture_but_not_diagnostics(
    private_home: Path, not_a_repo: Path, switch: str
) -> None:
    _cli(private_home, "disable", str(not_a_repo), **{switch: "off"})

    assert not _db(private_home).exists()
    assert "Completed disable via cli" in _log(private_home).read_text("utf-8")


def _rpc(proc: subprocess.Popen[str], message: dict[str, object]) -> None:
    assert proc.stdin is not None
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _reply(proc: subprocess.Popen[str]) -> dict[str, Any]:
    assert proc.stdout is not None
    line = proc.stdout.readline()
    reply: dict[str, Any] = json.loads(line)
    return reply


def test_mcp_entry_point_logs_to_file_and_keeps_stdout_for_json_rpc(
    private_home: Path, not_a_repo: Path
) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "punt_zspec", "mcp"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        env=_env(private_home),
    )
    try:
        _rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "0"},
                },
            },
        )
        assert _reply(proc)["id"] == 1
        _rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        _rpc(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "enablement",
                    "arguments": {"action": "disable", "directory": str(not_a_repo)},
                },
            },
        )
        reply = _reply(proc)
        assert reply["id"] == 2
        assert proc.stdin is not None
        proc.stdin.close()
        assert proc.wait(timeout=_TIMEOUT_S) == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    text = _log(private_home).read_text("utf-8")
    assert "Started MCP server" in text
    assert "Completed disable via mcp: outcome=failed" in text
    assert "Stopped MCP server" in text
    assert "z-spec.mcp.disable" in {name for name, _ in _events(private_home)}


def test_unreadable_report_records_one_invalid_report_failure(
    private_home: Path, tmp_path: Path
) -> None:
    spec = tmp_path / "s.tex"
    spec.write_text("", encoding="utf-8")

    proc = _cli(private_home, "partition", str(spec), "--report", "missing.json")

    assert proc.returncode == 1
    assert "error: cannot read report" in proc.stderr
    [(name, attrs)] = _events(private_home)
    assert name == "z-spec.cli.partition"
    assert attrs["outcome"] == "failed"
    assert attrs["failure"] == "invalid_report"


def test_concurrent_cli_processes_share_one_intact_log(
    private_home: Path, not_a_repo: Path
) -> None:
    writers = 6
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "punt_zspec", "disable", str(not_a_repo)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=_env(private_home, PYTHONFAULTHANDLER="1"),
        )
        for _ in range(writers)
    ]
    for proc in procs:
        _, stderr = proc.communicate(timeout=_TIMEOUT_S)
        assert proc.returncode == 1, stderr

    lines = _log(private_home).read_text("utf-8").splitlines()
    completed = [line for line in lines if "Completed disable via cli" in line]
    assert len(completed) == writers
    assert all(re.match(r"\d{4}-\d{2}-\d{2} ", line) for line in lines)
    assert len(_events(private_home)) == writers


def test_schemas_cover_every_capability_on_both_surfaces() -> None:
    declared = schemas()
    names = {schema.name for schema in declared}

    assert len(names) == len(declared) == 2 * len(CAPABILITIES)
    for capability in CAPABILITIES:
        assert signal_name("cli", capability.name) in names
        assert signal_name("mcp", capability.name) in names
    for schema in declared:
        assert re.fullmatch(r"z-spec\.(cli|mcp)\.[a-z_]+", schema.name)
        assert schema.version == SCHEMA_VERSION
        assert schema.kind == "event"


@pytest.mark.parametrize(
    ("version", "attrs", "verdict"),
    [
        (1, {}, None),
        (1, {"outcome": "ok", "duration_ms": 1.5}, None),
        (1, {"outcome": "failed", "failure": "spec_not_found"}, None),
        (2, {"outcome": "ok"}, "unknown_schema"),
        (1, {"path": "/home/user/spec.tex"}, "unknown_attribute"),
        (1, {"outcome": "spec text"}, "wrong_type"),
        (1, {"failure": "free text"}, "wrong_type"),
        (1, {"duration_ms": "1"}, "wrong_type"),
    ],
)
def test_schema_validation_rejects_unknown_and_free_text(
    version: int, attrs: dict[str, object], verdict: str | None
) -> None:
    registry = SchemaRegistry(schemas())

    result = registry.validate("z-spec.cli.check", version, attrs)

    if verdict is None:
        assert isinstance(result, dict)
    else:
        assert isinstance(result, str)


@final
class _CapturingMetricExporter(MetricExporter):
    """Accept metric batches without network or disk IO."""

    def export(
        self,
        metrics_data: MetricsData,
        timeout_millis: float = 10_000,
        **kwargs: object,
    ) -> MetricExportResult:
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        return True

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: object) -> None:
        return None


@final
class _FailingSpanExporter(SpanExporter):
    """An exporter whose every write fails, like a full disk or dead collector."""

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        raise OSError("disk full")


def _otlp(span_exporter: SpanExporter) -> TelemetryConfig:
    return TelemetryConfig(
        exporter="otlp",
        otlp_endpoint="http://unused.invalid",
        otlp_consent=True,
        exporter_factory=lambda _endpoint: (
            span_exporter,
            _CapturingMetricExporter(),
        ),
    )


def _failed() -> CommandResult[DoctorReport]:
    error = CommandError(CommandFailure.binary_missing, "fuzz not found")
    return CommandResult[DoctorReport].failed(error)


def test_exporter_swap_needs_no_reinstrumentation(private_home: Path) -> None:
    captured = InMemorySpanExporter()
    usage = Usage("mcp")
    usage.start(_otlp(captured))

    with usage.observe("doctor") as observed:
        observed.result(_failed())
    usage.stop()

    [span] = captured.get_finished_spans()
    assert span.name == "z-spec.mcp.doctor"
    assert dict(span.attributes or {})["failure"] == "binary_missing"
    assert not _db(private_home).exists()


def test_exporter_failure_never_changes_the_result(private_home: Path) -> None:
    usage = Usage("cli")
    usage.start(_otlp(_FailingSpanExporter()))
    result = _failed()

    with usage.observe("doctor") as observed:
        returned = observed.result(result)
    usage.stop()

    assert returned is result


def test_observe_records_error_and_reraises(private_home: Path) -> None:
    captured = InMemorySpanExporter()
    usage = Usage("cli")
    usage.start(_otlp(captured))

    with pytest.raises(RuntimeError, match="boom"), usage.observe("check"):
        raise RuntimeError("boom")
    usage.stop()

    [span] = captured.get_finished_spans()
    assert dict(span.attributes or {})["outcome"] == "error"
    assert "boom" not in json.dumps(dict(span.attributes or {}))


def test_unstarted_usage_opens_no_store(private_home: Path) -> None:
    usage = Usage("cli")

    with usage.observe("doctor") as observed:
        observed.result(_failed())
    usage.stop()

    assert not (private_home / ".punt-labs").exists()


def test_log_records_are_redacted_and_single_line(private_home: Path) -> None:
    path = DiagnosticLog.configure("cli")

    logging.getLogger("punt_zspec.test").warning(
        "fetch failed: %s", "https://u:SECRET@host/p?token=SECRET\nforged [INFO] x"
    )
    for handler in logging.getLogger().handlers:
        handler.flush()

    text = path.read_text("utf-8")
    assert "SECRET" not in text
    assert text.count("\n") == 1


def test_cli_exits_cleanly_when_home_cannot_be_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def no_home() -> Path:
        raise RuntimeError("Could not determine home directory.")

    monkeypatch.setattr(Path, "home", staticmethod(no_home))

    result = CliRunner().invoke(app, ["doctor"])

    assert result.exit_code == 1
    assert "error: cannot open the z-spec log" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_source_never_configures_logging_by_hand() -> None:
    banned = re.compile(r"basicConfig|RotatingFileHandler|logging\.handlers")
    offenders = [
        str(path.relative_to(_SRC))
        for path in sorted(_SRC.rglob("*.py"))
        if banned.search(path.read_text("utf-8"))
    ]

    assert offenders == []
