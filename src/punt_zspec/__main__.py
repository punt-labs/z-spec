"""Typer CLI for punt-zspec."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from punt_zspec import __version__
from punt_zspec.logging_config import DiagnosticLog, LoggingSetupError, Role
from punt_zspec.usage import Usage

if TYPE_CHECKING:
    from punt_zspec.commands.result import CommandResult, JsonObject
    from punt_zspec.types import Collection, EnablementReport, SpecModel, SpecReports

app = typer.Typer(
    name="z-spec",
    help="Z specification toolkit: type-check, model-check, and animate.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

_USAGE = Usage("cli")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"z-spec {__version__}")
        raise typer.Exit


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Z specification toolkit."""
    role: Role = "mcp" if ctx.invoked_subcommand == "mcp" else "cli"
    try:
        DiagnosticLog.configure(role)
    except LoggingSetupError as exc:
        typer.echo(f"error: cannot open the z-spec log: {exc}", err=True)
        raise typer.Exit(1) from exc
    if role == "cli":
        _USAGE.start()
        ctx.call_on_close(_USAGE.stop)


_TEX_ARG = typer.Argument(
    help="Path to .tex Z spec", exists=True, file_okay=True, dir_okay=False
)

_TOML_ARG = typer.Argument(
    help="Path to manifest.toml", exists=True, file_okay=True, dir_okay=False
)

_REPORT_OPT = typer.Option("--report", help="Report JSON file, or - for stdin")


def _read_report(report: str) -> str:
    """Read authored report JSON from stdin (``-``) or a file path.

    A missing or unreadable file exits 1 with a clean message, no traceback.
    """
    if report == "-":
        return sys.stdin.read()
    try:
        return Path(report).read_text("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        typer.echo(f"error: cannot read report: {exc}", err=True)
        raise typer.Exit(1) from exc


def _payload[T: JsonObject](result: CommandResult[T], *, hint: bool = False) -> T:
    """Return *result*'s payload, or print its error to stderr and exit 1.

    With *hint*, the message ends in a full stop followed by any remediation
    hint, the form the binary-backed verbs print.
    """
    err = result.error
    if err is None:
        return result.unwrap()
    suffix = f".{f' {err.hint}' if err.hint else ''}" if hint else ""
    typer.echo(f"error: {err.message}{suffix}", err=True)
    raise typer.Exit(1)


@app.command()
def check(
    file: Annotated[Path, _TEX_ARG],
) -> None:
    """Type-check a Z specification with fuzz."""
    from punt_zspec.commands.check import CheckCommand

    with _USAGE.observe("check") as observed:
        result = observed.result(CheckCommand().run(file))
    fuzz = _payload(result, hint=True)
    if fuzz.ok:
        typer.echo(f"fuzz: {file.name} OK")
        return
    typer.echo(f"fuzz: {file.name} FAIL", err=True)
    for e in fuzz.errors:
        typer.echo(f"  {e.line}:{e.column}: {e.message}", err=True)
    raise typer.Exit(1)


@app.command()
def test(
    file: Annotated[Path, _TEX_ARG],
    setsize: Annotated[
        int, typer.Option("--setsize", "-s", help="Default set size")
    ] = 2,
    max_ops: Annotated[int, typer.Option("--max-ops", help="Max operations")] = 1000,
    timeout: Annotated[
        int, typer.Option("--timeout", "-t", help="Timeout in ms")
    ] = 30000,
) -> None:
    """Run full probcli test suite and save report."""
    from punt_zspec.commands.options import ProbOptions
    from punt_zspec.commands.test import TestCommand

    options = ProbOptions(setsize=setsize, max_ops=max_ops, timeout_ms=timeout)
    with _USAGE.observe("test") as observed:
        result = observed.result(TestCommand().run(file, options))
    report = _payload(result, hint=True)
    typer.echo(json.dumps(report.to_dict(), indent=2))
    if not report.ok:
        raise typer.Exit(1)


@app.command()
def animate(
    file: Annotated[Path, _TEX_ARG],
    steps: Annotated[int, typer.Option("--steps", "-n", help="Animation steps")] = 20,
    setsize: Annotated[
        int, typer.Option("--setsize", "-s", help="Default set size")
    ] = 2,
) -> None:
    """Animate a Z specification with probcli."""
    from punt_zspec.commands.animate import AnimateCommand
    from punt_zspec.commands.options import AnimateOptions

    with _USAGE.observe("animate") as observed:
        result = observed.result(
            AnimateCommand().run(file, AnimateOptions(steps=steps, setsize=setsize))
        )
    report = _payload(result, hint=True)
    typer.echo(json.dumps(report.to_dict(), indent=2))
    if not report.ok:
        raise typer.Exit(1)


@app.command(name="model-check")
def model_check(
    file: Annotated[Path, _TEX_ARG],
    setsize: Annotated[
        int, typer.Option("--setsize", "-s", help="Default set size")
    ] = 2,
    max_ops: Annotated[int, typer.Option("--max-ops", help="Max operations")] = 1000,
    timeout: Annotated[
        int, typer.Option("--timeout", "-t", help="Timeout in ms")
    ] = 30000,
) -> None:
    """Model-check a Z specification with probcli."""
    from punt_zspec.commands.model_check import ModelCheckCommand
    from punt_zspec.commands.options import ProbOptions

    options = ProbOptions(setsize=setsize, max_ops=max_ops, timeout_ms=timeout)
    with _USAGE.observe("model-check") as observed:
        result = observed.result(ModelCheckCommand().run(file, options))
    report = _payload(result, hint=True)
    typer.echo(json.dumps(report.to_dict(), indent=2))
    if not report.ok:
        raise typer.Exit(1)


@app.command()
def report(
    file: Annotated[Path, _TEX_ARG],
) -> None:
    """Load and display an existing report."""
    from punt_zspec.commands.report import ReportCommand

    with _USAGE.observe("report") as observed:
        result = observed.result(ReportCommand().run(file))
    err = result.error
    if err is not None:
        typer.echo(err.message, err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(result.unwrap().to_dict(), indent=2))


@app.command()
def partition(
    file: Annotated[Path, _TEX_ARG],
    report: Annotated[str, _REPORT_OPT] = "-",
) -> None:
    """Validate and persist an authored TTF partition report."""
    from punt_zspec.commands.partition import PartitionCommand

    raw = _read_report(report)
    with _USAGE.observe("partition") as observed:
        result = observed.result(PartitionCommand().run(file, raw))
    typer.echo(str(_payload(result).path))


@app.command()
def audit(
    file: Annotated[Path, _TEX_ARG],
    report: Annotated[str, _REPORT_OPT] = "-",
) -> None:
    """Validate and persist an authored test-coverage audit report."""
    from punt_zspec.commands.audit import AuditCommand

    raw = _read_report(report)
    with _USAGE.observe("audit") as observed:
        result = observed.result(AuditCommand().run(file, raw))
    typer.echo(str(_payload(result).path))


@app.command()
def show(
    file: Annotated[Path, _TEX_ARG],
) -> None:
    """Display a Z specification and its reports in lux."""
    from punt_zspec.applet import build_z_spec_scene
    from punt_zspec.commands.show import ShowCommand
    from punt_zspec.display import LuxDisplay

    def build(spec: Path, model: SpecModel, reports: SpecReports) -> object:
        return build_z_spec_scene(
            spec,
            model,
            report=reports.report,
            fuzz=reports.fuzz,
            partition=reports.partition,
            audit=reports.audit,
        )

    with _USAGE.observe("show") as observed:
        result = observed.result(
            ShowCommand(build=build, display=LuxDisplay()).run(file)
        )
    _payload(result)
    typer.echo(result.to_json())


@app.command()
def browse(
    manifest: Annotated[Path, _TOML_ARG],
) -> None:
    """Open a Z spec collection in the tutorial browser."""
    from punt_zspec.browser import build_browser_scene
    from punt_zspec.commands.browse import BrowseCommand
    from punt_zspec.display import LuxDisplay

    def build(collection: Collection, specs: list[tuple[SpecModel, Path]]) -> object:
        return build_browser_scene(collection, specs)

    with _USAGE.observe("browse") as observed:
        result = observed.result(
            BrowseCommand(build=build, display=LuxDisplay()).run(manifest)
        )
    _payload(result)
    typer.echo(result.to_json())


@app.command()
def pick(
    directory: Annotated[
        Path,
        typer.Argument(
            help="Directory to search for .tex Z specs",
            exists=True,
            file_okay=False,
            dir_okay=True,
        ),
    ] = Path(),
) -> None:
    """Discover a directory's Z specs and display them in a picker."""
    from punt_zspec.commands.picker import PickerCommand
    from punt_zspec.display import LuxDisplay
    from punt_zspec.picker_scene import build_spec_picker

    # build_spec_picker satisfies PickerSceneBuilder structurally — pass it directly.
    with _USAGE.observe("pick") as observed:
        result = observed.result(
            PickerCommand(build=build_spec_picker, display=LuxDisplay()).run(directory)
        )
    _payload(result)
    typer.echo(result.to_json())


@app.command()
def doctor() -> None:
    """Check Z specification environment health."""
    from punt_zspec.commands.doctor import DoctorCommand

    with _USAGE.observe("doctor") as observed:
        health = observed.result(DoctorCommand().run()).unwrap()
    typer.echo(f"z-spec {health.version}")
    fuzz_status = f"OK ({health.fuzz})" if health.fuzz else "NOT FOUND"
    prob_status = f"OK ({health.probcli})" if health.probcli else "NOT FOUND"
    typer.echo(f"  fuzz:    {fuzz_status}")
    typer.echo(f"  probcli: {prob_status}")

    if not health.healthy:
        raise typer.Exit(1)


_DIR_ARG = typer.Argument(
    help="Directory inside the repository to change",
    exists=True,
    file_okay=False,
    dir_okay=True,
)


def _echo_enablement(result: CommandResult[EnablementReport]) -> None:
    """Print an enablement outcome, or exit 1 with the failure on stderr.

    Shared by both verbs so either renders identically (§2.14); the report
    owns the wording.
    """
    err = result.error
    if err is not None:
        typer.echo(f"error: {err.message}. {err.hint}", err=True)
        raise typer.Exit(1)
    typer.echo(result.unwrap().render())


@app.command()
def enable(
    directory: Annotated[Path, _DIR_ARG] = Path(),
) -> None:
    """Turn z-spec on in this repository."""
    from punt_zspec.commands.enable import EnableCommand

    with _USAGE.observe("enable") as observed:
        result = observed.result(EnableCommand().run(directory))
    _echo_enablement(result)


@app.command()
def disable(
    directory: Annotated[Path, _DIR_ARG] = Path(),
) -> None:
    """Turn z-spec off in this repository, leaving its files dormant."""
    from punt_zspec.commands.disable import DisableCommand

    with _USAGE.observe("disable") as observed:
        result = observed.result(DisableCommand().run(directory))
    _echo_enablement(result)


@app.command()
def mcp() -> None:
    """Start the MCP server (stdio transport)."""
    from punt_zspec.server import mcp as mcp_server

    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    app()
