"""Typer CLI for punt-zspec."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import typer

from punt_zspec import __version__

if TYPE_CHECKING:
    from punt_zspec.types import Collection, SpecModel, SpecReports

app = typer.Typer(
    name="z-spec",
    help="Z specification toolkit: type-check, model-check, and animate.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"z-spec {__version__}")
        raise typer.Exit


@app.callback()
def main(
    version: Annotated[
        bool | None,
        typer.Option("--version", "-V", callback=_version_callback, is_eager=True),
    ] = None,
) -> None:
    """Z specification toolkit."""


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


@app.command()
def check(
    file: Annotated[Path, _TEX_ARG],
) -> None:
    """Type-check a Z specification with fuzz."""
    from punt_zspec.commands.check import CheckCommand

    result = CheckCommand().run(file)
    err = result.error
    if err is not None:
        suffix = f" {err.hint}" if err.hint else ""
        typer.echo(f"error: {err.message}.{suffix}", err=True)
        raise typer.Exit(1)
    fuzz = result.unwrap()
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
    result = TestCommand().run(file, options)
    err = result.error
    if err is not None:
        suffix = f" {err.hint}" if err.hint else ""
        typer.echo(f"error: {err.message}.{suffix}", err=True)
        raise typer.Exit(1)
    report = result.unwrap()
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

    result = AnimateCommand().run(file, AnimateOptions(steps=steps, setsize=setsize))
    err = result.error
    if err is not None:
        suffix = f" {err.hint}" if err.hint else ""
        typer.echo(f"error: {err.message}.{suffix}", err=True)
        raise typer.Exit(1)
    report = result.unwrap()
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
    result = ModelCheckCommand().run(file, options)
    err = result.error
    if err is not None:
        suffix = f" {err.hint}" if err.hint else ""
        typer.echo(f"error: {err.message}.{suffix}", err=True)
        raise typer.Exit(1)
    report = result.unwrap()
    typer.echo(json.dumps(report.to_dict(), indent=2))
    if not report.ok:
        raise typer.Exit(1)


@app.command()
def report(
    file: Annotated[Path, _TEX_ARG],
) -> None:
    """Load and display an existing report."""
    from punt_zspec.commands.report import ReportCommand

    result = ReportCommand().run(file)
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
    result = PartitionCommand().run(file, raw)
    err = result.error
    if err is not None:
        typer.echo(f"error: {err.message}", err=True)
        raise typer.Exit(1)
    typer.echo(str(result.unwrap().path))


@app.command()
def audit(
    file: Annotated[Path, _TEX_ARG],
    report: Annotated[str, _REPORT_OPT] = "-",
) -> None:
    """Validate and persist an authored test-coverage audit report."""
    from punt_zspec.commands.audit import AuditCommand

    raw = _read_report(report)
    result = AuditCommand().run(file, raw)
    err = result.error
    if err is not None:
        typer.echo(f"error: {err.message}", err=True)
        raise typer.Exit(1)
    typer.echo(str(result.unwrap().path))


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

    result = ShowCommand(build=build, display=LuxDisplay()).run(file)
    err = result.error
    if err is not None:
        typer.echo(f"error: {err.message}", err=True)
        raise typer.Exit(1)
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

    result = BrowseCommand(build=build, display=LuxDisplay()).run(manifest)
    err = result.error
    if err is not None:
        typer.echo(f"error: {err.message}", err=True)
        raise typer.Exit(1)
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
    from punt_zspec.browser import build_spec_picker
    from punt_zspec.commands.picker import PickerCommand
    from punt_zspec.display import LuxDisplay

    def build(specs: list[tuple[Path, SpecModel]]) -> object:
        return build_spec_picker(specs)

    result = PickerCommand(build=build, display=LuxDisplay()).run(directory)
    err = result.error
    if err is not None:
        typer.echo(f"error: {err.message}", err=True)
        raise typer.Exit(1)
    typer.echo(result.to_json())


@app.command()
def doctor() -> None:
    """Check Z specification environment health."""
    from punt_zspec.commands.doctor import DoctorCommand

    health = DoctorCommand().run().unwrap()
    typer.echo(f"z-spec {health.version}")
    fuzz_status = f"OK ({health.fuzz})" if health.fuzz else "NOT FOUND"
    prob_status = f"OK ({health.probcli})" if health.probcli else "NOT FOUND"
    typer.echo(f"  fuzz:    {fuzz_status}")
    typer.echo(f"  probcli: {prob_status}")

    if not health.healthy:
        raise typer.Exit(1)


@app.command()
def mcp() -> None:
    """Start the MCP server (stdio transport)."""
    from punt_zspec.server import mcp as mcp_server

    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    app()
