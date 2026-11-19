---
paths:
  - "**/*.py"
---

# Logging & Telemetry

**Introduced:** 2026-11-19

Implement the language-neutral [Logging policy](https://github.com/punt-labs/punt-kit/blob/main/standards/logging.md)
and [Telemetry policy](https://github.com/punt-labs/punt-kit/blob/main/standards/telemetry.md).
Consumer tests below are required acceptance cases, not tests supplied by
punt-kit. Review is a gate, not a claim of automated runtime coverage.

## PY-LOG-1: Shared Configuration

**Implements:** LOG-1, LOG-5, TEL-1, TEL-2

**Statement**: Use one shared Punt Labs package, provisionally `punt-observe`:
`punt_observe.logging` owns diagnostic setup; `punt_observe.telemetry` wraps
`opentelemetry-api` spans, events and metrics. Keep pipelines separate. Tool
instrumentation imports only the shared telemetry API, never exporters.
Exporter selection is configuration, not instrumentation. Do not hand-roll
or vendor copies. Follow vox's `AtomicAppendLog` and quarry's `LogRedactor`.

Own setup in `logging_config.py`. Each entry point calls
`configure_logging(tool, role, ...)`; libraries never configure logging.
The shared implementation uses `logging.config.dictConfig`, never `basicConfig`.
The tool-facing adapter has this shape (the shared-package API contract):

```python
"""Configure diagnostics for tool entry points."""

from __future__ import annotations

from punt_observe.logging import configure_logging as _configure_logging


def configure_logging(tool: str, role: str, *, stderr_level: str = "WARNING") -> None:
    """Configure a private durable sink and optional terminal diagnostics."""
    _configure_logging(tool, role, stderr_level=stderr_level)
```

Inside the shared configurator, use this `dictConfig` structure, where
`file_handler_factory` creates a compliant private, redacting handler:

```python
logging.config.dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "file": {
                "()": file_handler_factory,
                "level": "INFO",
                "formatter": "standard",
            },
            "stderr": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stderr",
                "level": stderr_level,
                "formatter": "standard",
            },
        },
        "root": {"level": "DEBUG", "handlers": ["file", "stderr"]},
    }
)
```

Suppress noisy dependencies, including the MCP framework request logger,
through the `loggers` configuration at WARNING.

**Gate:** Review entry points, import boundaries and the sink map. Require
consumer tests for separate diagnostic/usage pipelines and exporter-only migration.

## PY-LOG-2: Module Loggers and Lazy Arguments

**Implements:** LOG-5, LOG-14

**Statement**: Declare `logger = logging.getLogger(__name__)` at module scope.
Do not use the root logger directly or pass logger instances between modules.
Use `%`-style lazy arguments, not f-strings, `str.format` or precomputed `%`
interpolation. For untrusted values use escaped arguments, for example
`logger.warning("rejected unknown signal %r", signal)`. `%r` is a useful default,
not a replacement for final-record escaping of every forbidden separator.
Operational `print()` is forbidden; intentional CLI output gets narrow exemptions.

**Gate:** Ruff `LOG`, `G`, `T20` (existing checks; select explicitly in consumer
configuration); review module declarations and escaping semantics.

## PY-LOG-3: Private Storage

**Implements:** LOG-7, LOG-8, TEL-5, TEL-6

**Statement**: Resolve logs with `Path.home() / ".punt-labs" / tool / "logs"`.
Set directory mode `0o700` and active/backup file modes `0o600`, including
pre-existing files. Use `os.open(path, flags, 0o600)` at creation, not `open()`
followed by `chmod()`. Tighten backups at startup and rollover. Surface startup
permission failures outside the handler; never recurse into a failing handler
to report its own write-path tightening failure.

For telemetry, follow quarry's `telemetry_perms.TelemetryPathGuard`: secure the
directory, pre-create the leaf with `os.open(..., O_CREAT | O_EXCL, 0o600)`
before SQLite opens it, and tighten existing files. Protect SQLite sidecars
and the per-install random salt. Raw identifiers and the salt never enter payloads.

**Gate:** Review; require consumer tests for new/existing files, backups,
sidecars, salt and denied permission changes.

## PY-LOG-4: Multi-Process-Safe Rotation

**Implements:** LOG-10, LOG-11

**Statement**: Keep `maxBytes=5_242_880` and `backupCount=5`. Stdlib
`RotatingFileHandler` and `TimedRotatingFileHandler`, including subclasses,
aliases and configuration strings, are forbidden for multi-writer files.
An exception requires reviewed proof of single-process ownership. Plain
stdlib handlers also do not guarantee private creation or backup permissions.

Use vox's `AtomicAppendLog` mechanism: atomic `O_APPEND`, an `fcntl` lock file
serializing rotation, and reopening when the inode changes. A `QueueHandler`
alone coordinates neither processes nor rotation. Use it only when all writers
route to a single listener owning the file, not per-process rotating listeners.

**Gate:** Review process topology; require concurrent-writer rollover tests
for loss, corruption, bounded storage and private backups. The unsafe-handler
source check in PY-LOG-9 is planned, not supplied here.

## PY-LOG-5: Redaction and Injection Safety

**Implements:** LOG-2, LOG-6, LOG-14, LOG-15

**Statement**: Apply quarry's `LogRedactor` semantics to the final formatted
record, including exception text and tracebacks, before writing. A filter
touching only `record.msg` is insufficient. Enforce the policy's credential/URL
masking, control-character escaping and 64 KiB cap; withhold unsettled records.
Redaction is not permission to log content. Log security decisions at WARNING
with metadata, never rejected content.

The reference escape table is:

```python
_SANITIZE = {c: f"\\x{c:02x}" for c in (*range(0x20), *range(0x7F, 0xA0))}
_SANITIZE.update({cp: f"\\u{cp:04x}" for cp in (0x85, 0x2028, 0x2029)})
```

Apply `str(value).translate(_SANITIZE)` before interpolation where needed.

**Gate:** Review; require consumer tests for empty input, credentials/URLs,
tracebacks, size limits, redactor failure and forged-line/control sequences.

## PY-LOG-6: Diagnostic Semantics and Entry Points

**Implements:** LOG-3, LOG-4, LOG-9, LOG-12, LOG-13, LOG-16

**Statement**: Configure CLI, MCP, hook, daemon and detached worker roles.
Workers spawned with `start_new_session=True` configure their own sink at
their entry point even with stderr set to `subprocess.DEVNULL`. Keep stdout
reserved for MCP stdio. Document process-to-file sinks; avoid daemon stderr
file redirects. Log decisions, state changes, boundary crosses and symmetric
outcomes once, with plain-language INFO. Put internal dumps at DEBUG, use
actionable WARNINGs and reserve ERROR for unexpected operation failure.
Correlate spawn intent with child startup, completion and failure.

**Gate:** Review semantics and sink maps; require consumer tests for every
entry point and detached failures. Inspect the running system's durable files,
not merely mocked logger calls.

## PY-LOG-7: Typed Telemetry Boundary

**Implements:** TEL-3, TEL-4, TEL-5

**Statement**: Declare versioned schemas in the shared API with typed
allowlists, closed enums and explicit units. Reject arbitrary strings,
unknown fields/versions and wrong types before enqueueing. Use
`<tool>.<surface>.<action>` names and OTel semantic conventions. Reject content
across spans, events, metrics, resources, status and automatic exceptions.
Only schema-declared lengths and per-install salted hashes may derive from
content. No automatic instrumentation may bypass validation.

**Gate:** Review; require consumer tests for valid/empty attributes, unknown
fields/versions, wrong types, content rejection and salted derivation without
raw identifiers entering the queue.

## PY-LOG-8: Export, Controls and Isolation

**Implements:** TEL-2, TEL-6, TEL-7, TEL-8, TEL-9, TEL-10

**Statement**: The shared package owns SQLite and OTLP/HTTP exporters. Retain
90 days by default (quarry's `Settings.telemetry_retention_days` reference);
prune at startup and periodically, reclaim expired space and forbid unlimited
retention. Local capture defaults on; network export requires opt-in. Any off
switch wins: `PUNT_TELEMETRY=off`, per-tool config or `<TOOL>_TELEMETRY=off`.
When off, open no store and start no worker/exporter.

Use a bounded non-blocking queue, drop on saturation and bound I/O and shutdown
flush time. Swallow exporter errors; rate-limit metadata-only diagnostic
reporting. Telemetry cannot change the tool's result.

**Gate:** Review; require consumer tests for retention/reclamation, consent,
off-switch combinations and no store while off, saturation, full disk/unwritable
store, exporter failure, bounded shutdown and exporter-only migration.

## PY-LOG-9: Enforcement and Traceability

**Implements:** LOG-5, LOG-11, LOG-14

**Statement**: Select Ruff `LOG`, `G`, `T20`. A consumer source check MUST ban
`basicConfig` and unsafe stdlib rotating handlers in `src/`, including aliases,
subclasses and `dictConfig` strings; allow handlers only with reviewed proof
of single ownership. Ruff cannot enforce these bans. The source check is
planned; until provided, review is the gate.

**Gate:** Ruff codes plus review. `make check-standards`, included
in `make lint` and `make check`, checks policy citation coverage, dangling
citations and duplicate definitions, not implementation correctness.

## Policy Traceability

Every policy ID maps to a rule and gate. An explicit row with Python rule(s)
`gap` and gate `gap` records a policy without claiming implementation; only
`Implements` lines count as citations. Review is a gate, not
automated runtime coverage. Planned source checks and required consumer tests
are not represented as existing automated checks. There are no unmapped clauses.

| Policy ID | Python rule(s) | Gate |
|-----------|----------------|------|
| LOG-1 | PY-LOG-1 | Review |
| LOG-2 | PY-LOG-5 | Review; consumer privacy tests required |
| LOG-3 | PY-LOG-6 | Review |
| LOG-4 | PY-LOG-6 | Review; running sink inspection |
| LOG-5 | PY-LOG-1, PY-LOG-2, PY-LOG-9 | Review; Ruff LOG/G/T20; source check planned |
| LOG-6 | PY-LOG-5 | Review; consumer redaction tests required |
| LOG-7 | PY-LOG-3 | Review |
| LOG-8 | PY-LOG-3 | Review; consumer permission tests required |
| LOG-9 | PY-LOG-6 | Review |
| LOG-10 | PY-LOG-4 | Review; consumer rollover tests required |
| LOG-11 | PY-LOG-4, PY-LOG-9 | Review; consumer concurrency tests required; source check planned |
| LOG-12 | PY-LOG-6 | Review |
| LOG-13 | PY-LOG-6 | Review |
| LOG-14 | PY-LOG-2, PY-LOG-5, PY-LOG-9 | Ruff G; review; consumer injection tests required |
| LOG-15 | PY-LOG-5 | Review |
| LOG-16 | PY-LOG-6 | Review; consumer detached-worker tests required |
| TEL-1 | PY-LOG-1 | Review |
| TEL-2 | PY-LOG-1, PY-LOG-8 | Review; consumer exporter-swap test required |
| TEL-3 | PY-LOG-7 | Review; consumer schema tests required |
| TEL-4 | PY-LOG-7 | Review; consumer content-rejection tests required |
| TEL-5 | PY-LOG-3, PY-LOG-7 | Review; consumer salt/derivation tests required |
| TEL-6 | PY-LOG-3, PY-LOG-8 | Review; consumer SQLite permission tests required |
| TEL-7 | PY-LOG-8 | Review; consumer retention tests required |
| TEL-8 | PY-LOG-8 | Review; consumer export-consent tests required |
| TEL-9 | PY-LOG-8 | Review; consumer off-switch tests required |
| TEL-10 | PY-LOG-8 | Review; consumer isolation tests required |
