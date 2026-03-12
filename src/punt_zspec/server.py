"""FastMCP server for punt-zspec — grimoire API."""

from __future__ import annotations

import json
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from punt_zspec import __version__

mcp = FastMCP(
    "grimoire",
    instructions=(
        "Z specification toolkit. Use these tools to type-check Z specs "
        "with fuzz, model-check with probcli, and display specs in lux."
    ),
)
mcp._mcp_server.version = __version__  # pyright: ignore[reportPrivateUsage]


@mcp.tool()
def check(file: str) -> str:
    """Type-check a Z specification with fuzz.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON with ok (bool) and errors (list).
    """
    from punt_zspec.fuzz import resolve_fuzz, run_fuzz

    path = Path(file)
    binary = resolve_fuzz()
    if binary is None:
        return json.dumps({"ok": False, "error": "fuzz not found"})
    result = run_fuzz(path, binary)
    return json.dumps(result.to_dict())


@mcp.tool()
def test(
    file: str,
    setsize: int = 2,
    max_ops: int = 1000,
    timeout: int = 30000,
) -> str:
    """Run full probcli test suite and save report.

    Args:
        file: Path to the .tex Z specification file.
        setsize: Default set size for model checking.
        max_ops: Maximum operations to explore.
        timeout: Timeout in milliseconds.

    Returns:
        JSON report with all check results.
    """
    from punt_zspec.prob import resolve_probcli, run_full_suite
    from punt_zspec.report import save_report

    path = Path(file)
    binary = resolve_probcli()
    if binary is None:
        return json.dumps({"ok": False, "error": "probcli not found"})
    rpt = run_full_suite(
        path, binary, setsize=setsize, max_ops=max_ops, timeout_ms=timeout
    )
    save_report(path, rpt)
    return json.dumps(rpt.to_dict())


@mcp.tool()
def animate(file: str, steps: int = 20, setsize: int = 2) -> str:
    """Animate a Z specification with probcli.

    Args:
        file: Path to the .tex Z specification file.
        steps: Number of animation steps.
        setsize: Default set size.

    Returns:
        JSON report with animation results.
    """
    from punt_zspec.prob import resolve_probcli, run_animate
    from punt_zspec.report import save_report

    path = Path(file)
    binary = resolve_probcli()
    if binary is None:
        return json.dumps({"ok": False, "error": "probcli not found"})
    rpt = run_animate(path, binary, steps=steps, setsize=setsize)
    save_report(path, rpt)
    return json.dumps(rpt.to_dict())


@mcp.tool()
def model_check(
    file: str,
    setsize: int = 2,
    max_ops: int = 1000,
    timeout: int = 30000,
) -> str:
    """Model-check a Z specification with probcli.

    Args:
        file: Path to the .tex Z specification file.
        setsize: Default set size for model checking.
        max_ops: Maximum operations to explore.
        timeout: Timeout in milliseconds.

    Returns:
        JSON report with model checking results.
    """
    from punt_zspec.prob import resolve_probcli, run_model_check
    from punt_zspec.report import save_report

    path = Path(file)
    binary = resolve_probcli()
    if binary is None:
        return json.dumps({"ok": False, "error": "probcli not found"})
    rpt = run_model_check(
        path, binary, setsize=setsize, max_ops=max_ops, timeout_ms=timeout
    )
    save_report(path, rpt)
    return json.dumps(rpt.to_dict())


@mcp.tool()
def show_z_spec(file: str) -> str:
    """Parse a Z spec and render it in the lux applet.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON with spec model and applet status.
    """
    from punt_zspec.applet import show_applet
    from punt_zspec.parser import parse_spec
    from punt_zspec.report import load_report

    path = Path(file)
    spec = parse_spec(path)
    rpt = load_report(path)
    result = show_applet(path, spec, rpt)
    return json.dumps(result)


@mcp.tool()
def get_report(file: str) -> str:
    """Load an existing ProB report for a Z specification.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON report or error if no report exists.
    """
    from punt_zspec.report import load_report

    path = Path(file)
    rpt = load_report(path)
    if rpt is None:
        return json.dumps({"ok": False, "error": f"No report found for {path.name}"})
    return json.dumps(rpt.to_dict())
