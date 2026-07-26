"""Typer CLI for punt-zspec."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from punt_zspec import __version__

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
