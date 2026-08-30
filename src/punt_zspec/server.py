"""FastMCP server for punt-zspec."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import FastMCP

from punt_zspec import __version__
from punt_zspec.commands.enablement import RepoEnablement
from punt_zspec.server_context import ServerContext
from punt_zspec.types import EnablementAction

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from punt_zspec.types import Collection, SpecModel, SpecReports

# The module's one public name: every tool is reached through the server, and
# the lifespan is FastMCP's to call (PL-CU-3).
__all__ = ["lifespan", "mcp"]


_ctx = ServerContext()


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncGenerator[None]:
    """Delegate lifespan management to the process's shared server context.

    A named module-level function, not a bare ``lifespan = _ctx.lifespan``
    alias, for two reasons. Measured: the alias regresses this module's
    avg_params from 1.87 (the committed baseline) to 1.93 — the OO ratchet
    rules it out, not a style preference. Exported: ``lifespan`` is the one
    name this module promises FastMCP and the plugin tests (PL-CU-3), and a
    bound method borrowed from an internal singleton is a worse public
    symbol than a plain function this module owns outright.
    """
    async with _ctx.lifespan(server):
        yield


mcp = FastMCP(
    "zspec",
    instructions=(
        "Z specification toolkit. Use these tools to type-check Z specs "
        "with fuzz, model-check with probcli, and display specs in lux."
    ),
    lifespan=lifespan,
)
if hasattr(mcp, "_mcp_server") and hasattr(mcp._mcp_server, "version"):  # pyright: ignore[reportPrivateUsage]
    mcp._mcp_server.version = __version__  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
@_ctx.guard
def check(file: str) -> str:
    """Type-check a Z specification with fuzz.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON: on success {ok: true, errors: [...]}, on failure
        {ok: false, error: <str>}.
    """
    from punt_zspec.commands.check import CheckCommand

    return CheckCommand().run(Path(file)).to_json()


@mcp.tool()
@_ctx.guard
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
    from punt_zspec.commands.options import ProbOptions
    from punt_zspec.commands.test import TestCommand

    options = ProbOptions(setsize=setsize, max_ops=max_ops, timeout_ms=timeout)
    return TestCommand().run(Path(file), options).to_json()


@mcp.tool()
@_ctx.guard
def animate(file: str, steps: int = 20, setsize: int = 2) -> str:
    """Animate a Z specification with probcli.

    Args:
        file: Path to the .tex Z specification file.
        steps: Number of animation steps.
        setsize: Default set size.

    Returns:
        JSON report with animation results.
    """
    from punt_zspec.commands.animate import AnimateCommand
    from punt_zspec.commands.options import AnimateOptions

    options = AnimateOptions(steps=steps, setsize=setsize)
    return AnimateCommand().run(Path(file), options).to_json()


@mcp.tool()
@_ctx.guard
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
    from punt_zspec.commands.model_check import ModelCheckCommand
    from punt_zspec.commands.options import ProbOptions

    options = ProbOptions(setsize=setsize, max_ops=max_ops, timeout_ms=timeout)
    return ModelCheckCommand().run(Path(file), options).to_json()


@mcp.tool()
@_ctx.guard
def doctor() -> str:
    """Report Z-toolkit environment health.

    Returns:
        JSON with version, resolved fuzz/probcli paths, and healthy (bool).
    """
    from punt_zspec.commands.doctor import DoctorCommand

    return DoctorCommand().run().to_json()


@mcp.tool()
@_ctx.guard
def show(file: str) -> str:
    """Parse a Z spec and display it in lux.

    Loads all available reports (fuzz, ProB, partition, audit) and
    renders each as a tab alongside the Spec tab.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON with ok (bool) and scene_id on success, or error.
    """
    from punt_zspec.applet import build_z_spec_scene
    from punt_zspec.commands.show import ShowCommand

    def build(spec: Path, model: SpecModel, reports: SpecReports) -> object:
        return build_z_spec_scene(
            spec,
            model,
            report=reports.report,
            fuzz=reports.fuzz,
            partition=reports.partition,
            audit=reports.audit,
        )

    return ShowCommand(build=build, display=_ctx.display).run(Path(file)).to_json()


@mcp.tool()
@_ctx.guard
def report(file: str) -> str:
    """Load an existing ProB report for a Z specification.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON report or error if no report exists.
    """
    from punt_zspec.commands.report import ReportCommand

    return ReportCommand().run(Path(file)).to_json()


@mcp.tool()
@_ctx.guard
def partition(file: str, report_json: str) -> str:
    """Validate and save a partition report for a Z specification.

    The report is saved as <stem>.partition.json alongside the .tex file.

    Args:
        file: Path to the .tex Z specification file.
        report_json: JSON string matching the partition report schema.

    Returns:
        JSON with ok (bool) and path to saved report.
    """
    from punt_zspec.commands.partition import PartitionCommand

    return PartitionCommand().run(Path(file), report_json).to_json()


@mcp.tool()
@_ctx.guard
def browse(manifest: str) -> str:
    """Open a Z spec collection in the tutorial browser.

    Parses a manifest.toml and displays all lessons in a tabbed lux view.
    Navigation is instant and display-side — no round-trips.

    Args:
        manifest: Path to the manifest.toml file.

    Returns:
        JSON with ok (bool), total lessons, and collection title.
    """
    from punt_zspec.browser import build_browser_scene
    from punt_zspec.commands.browse import BrowseCommand

    def build(collection: Collection, specs: list[tuple[SpecModel, Path]]) -> object:
        return build_browser_scene(collection, specs)

    return (
        BrowseCommand(build=build, display=_ctx.display).run(Path(manifest)).to_json()
    )


@mcp.tool()
@_ctx.guard
def pick(directory: str = _ctx.project_dir) -> str:
    """Discover a directory's Z specs and display them in a tabbed picker.

    Globs ``directory`` for ``.tex`` specs (skipping templates and LaTeX
    includes that carry no Z blocks) and renders one tab per spec. This is the
    same command the Browse right-click menu entry runs.

    Args:
        directory: Directory to search for .tex Z specs. Defaults to the
            project root, the same directory the Browse menu entry targets.

    Returns:
        JSON with ok (bool), total specs, and scene_id on success, or error.
    """
    from punt_zspec.commands.picker import PickerCommand
    from punt_zspec.picker_scene import build_spec_picker

    # build_spec_picker satisfies PickerSceneBuilder structurally — pass it directly.
    return (
        PickerCommand(build=build_spec_picker, display=_ctx.display)
        .run(Path(directory))
        .to_json()
    )


@mcp.tool()
async def enablement(
    action: Literal["enable", "disable"], directory: str = _ctx.project_dir
) -> str:
    """Turn z-spec on or off in this repository.

    Enabling deposits `.punt-labs/z-spec/CLAUDE.md`, writes the
    `.punt-labs/z-spec/enabled` marker, and adds the `@`-import line to the
    repo `CLAUDE.md`. Disabling removes the import line and the marker and
    leaves the rest of `.punt-labs/z-spec/` dormant. Enabling is idempotent and
    is also the upgrade path. Neither runs git: commit the marker in a PR.

    Both verbs take effect immediately, on the menu as well as on the tools:
    enabling brings the Tutorial and Browse entries up on the shared lux window
    and disabling takes them down, with no server reconnect either way.

    Args:
        action: "enable" or "disable".
        directory: Directory inside the repository to act on. Defaults to the
            project root Claude Code has open.

    Returns:
        JSON with ok (bool), action, enabled (bool), and the marker, guide,
        and import_line paths, or error.
    """
    # Off-thread: the working-tree writes block, and this is the one tool that
    # runs on the loop the listener shares (ADR §5.3).
    result = await asyncio.to_thread(
        RepoEnablement.apply, EnablementAction(action), Path(directory)
    )
    await _ctx.sync()
    return result.to_json()


@mcp.tool()
@_ctx.guard
def audit(file: str, report_json: str) -> str:
    """Validate and save an audit report for a Z specification.

    The report is saved as <stem>.audit.json alongside the .tex file.

    Args:
        file: Path to the .tex Z specification file.
        report_json: JSON string matching the audit report schema.

    Returns:
        JSON with ok (bool) and path to saved report.
    """
    from punt_zspec.commands.audit import AuditCommand

    return AuditCommand().run(Path(file), report_json).to_json()
