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
    from punt_zspec.fuzz import resolve_fuzz, run_fuzz

    binary = resolve_fuzz()
    if binary is None:
        typer.echo("error: fuzz not found. Set $FUZZ or add fuzz to PATH.", err=True)
        raise typer.Exit(1)
    result = run_fuzz(file, binary)
    if result.ok:
        typer.echo(f"fuzz: {file.name} OK")
    else:
        typer.echo(f"fuzz: {file.name} FAIL", err=True)
        for err in result.errors:
            typer.echo(f"  {err.line}:{err.column}: {err.message}", err=True)
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
    from punt_zspec.prob import resolve_probcli, run_full_suite
    from punt_zspec.report import save_report

    binary = resolve_probcli()
    if binary is None:
        typer.echo(
            "error: probcli not found. Set $PROBCLI or add probcli to PATH.",
            err=True,
        )
        raise typer.Exit(1)
    report = run_full_suite(
        file, binary, setsize=setsize, max_ops=max_ops, timeout_ms=timeout
    )
    save_report(file, report)
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
    from punt_zspec.prob import resolve_probcli, run_animate
    from punt_zspec.report import save_report

    binary = resolve_probcli()
    if binary is None:
        typer.echo(
            "error: probcli not found. Set $PROBCLI or add probcli to PATH.",
            err=True,
        )
        raise typer.Exit(1)
    report = run_animate(file, binary, steps=steps, setsize=setsize)
    save_report(file, report)
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
    from punt_zspec.prob import resolve_probcli, run_model_check
    from punt_zspec.report import save_report

    binary = resolve_probcli()
    if binary is None:
        typer.echo(
            "error: probcli not found. Set $PROBCLI or add probcli to PATH.",
            err=True,
        )
        raise typer.Exit(1)
    report = run_model_check(
        file, binary, setsize=setsize, max_ops=max_ops, timeout_ms=timeout
    )
    save_report(file, report)
    typer.echo(json.dumps(report.to_dict(), indent=2))
    if not report.ok:
        raise typer.Exit(1)


@app.command()
def report(
    file: Annotated[Path, _TEX_ARG],
) -> None:
    """Load and display an existing report."""
    from punt_zspec.report import load_report

    rpt = load_report(file)
    if rpt is None:
        typer.echo(f"No report found for {file.name}", err=True)
        raise typer.Exit(1)
    typer.echo(json.dumps(rpt.to_dict(), indent=2))


@app.command()
def doctor() -> None:
    """Check Z specification environment health."""
    from punt_zspec.fuzz import resolve_fuzz
    from punt_zspec.prob import resolve_probcli

    fuzz_bin = resolve_fuzz()
    prob_bin = resolve_probcli()

    typer.echo(f"z-spec {__version__}")
    fuzz_status = f"OK ({fuzz_bin})" if fuzz_bin else "NOT FOUND"
    prob_status = f"OK ({prob_bin})" if prob_bin else "NOT FOUND"
    typer.echo(f"  fuzz:    {fuzz_status}")
    typer.echo(f"  probcli: {prob_status}")

    if fuzz_bin is None or prob_bin is None:
        raise typer.Exit(1)


@app.command()
def mcp() -> None:
    """Start the MCP server (stdio transport)."""
    from punt_zspec.server import mcp as mcp_server

    mcp_server.run(transport="stdio")


if __name__ == "__main__":
    app()
