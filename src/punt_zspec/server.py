"""FastMCP server for punt-zspec."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from mcp.server.fastmcp import FastMCP

from punt_zspec import __version__
from punt_zspec.commands.enablement import RepoEnablement
from punt_zspec.gate import EnablementGate
from punt_zspec.lux import ZSpecLuxSession
from punt_zspec.types import EnablementAction

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from punt_zspec.types import Collection, SpecModel, SpecReports

logger = logging.getLogger(__name__)

# The module's one public name: every tool is reached through the server, and
# the lifespan is FastMCP's to call (PL-CU-3).
__all__ = ["lifespan", "mcp"]


# One per MCP server process: the persistent app-identity lux client, the display
# every render tool shares, and the menu listener. Constructed lazily-connecting,
# so a down luxd never blocks import or the check/test/animate tool surface.
_SESSION = ZSpecLuxSession()

# The one gate (punt-kit tool-enable-disable.md §2.3). ``Path()`` is the
# process cwd — the repo Claude Code launched the server in — resolved afresh
# on each read, so no state outlives an ``enable`` run.
_GATE = EnablementGate(Path())


@asynccontextmanager
async def lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Start the menu listener on entry and drain it on shutdown (best-effort).

    In a repo with no marker the listener never starts, so z-spec contributes
    no entries to the shared lux menu. The plugin loads in every Claude Code
    session against one daemon serving one window; without this, every session
    would register its entries in every repo.
    """
    if not _GATE.is_open():
        logger.info("z-spec is not enabled here — lux menu registration skipped")
        yield
        return
    await _SESSION.start()
    try:
        yield
    finally:
        await _SESSION.stop()


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
@_GATE.guard
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
@_GATE.guard
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
@_GATE.guard
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
@_GATE.guard
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
@_GATE.guard
def doctor() -> str:
    """Report Z-toolkit environment health.

    Returns:
        JSON with version, resolved fuzz/probcli paths, and healthy (bool).
    """
    from punt_zspec.commands.doctor import DoctorCommand

    return DoctorCommand().run().to_json()


@mcp.tool()
@_GATE.guard
def show_z_spec(file: str) -> str:
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

    return ShowCommand(build=build, display=_SESSION.display).run(Path(file)).to_json()


@mcp.tool()
@_GATE.guard
def get_report(file: str) -> str:
    """Load an existing ProB report for a Z specification.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON report or error if no report exists.
    """
    from punt_zspec.commands.report import ReportCommand

    return ReportCommand().run(Path(file)).to_json()


@mcp.tool()
@_GATE.guard
def save_partition_report(file: str, report_json: str) -> str:
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
@_GATE.guard
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
        BrowseCommand(build=build, display=_SESSION.display)
        .run(Path(manifest))
        .to_json()
    )


@mcp.tool()
@_GATE.guard
def pick(directory: str = ".") -> str:
    """Discover a directory's Z specs and display them in a tabbed picker.

    Globs ``directory`` for ``.tex`` specs (skipping templates and LaTeX
    includes that carry no Z blocks) and renders one tab per spec. This is the
    same command the Browse right-click menu entry runs.

    Args:
        directory: Directory to search for .tex Z specs. Defaults to the cwd.

    Returns:
        JSON with ok (bool), total specs, and scene_id on success, or error.
    """
    from punt_zspec.browser import build_spec_picker
    from punt_zspec.commands.picker import PickerCommand

    # build_spec_picker matches PickerSceneBuilder(specs, root) — pass it directly.
    return (
        PickerCommand(build=build_spec_picker, display=_SESSION.display)
        .run(Path(directory))
        .to_json()
    )


@mcp.tool()
def enablement(action: Literal["enable", "disable"], directory: str = ".") -> str:
    """Turn z-spec on or off in this repository.

    Enabling deposits `.punt-labs/z-spec/CLAUDE.md`, writes the
    `.punt-labs/z-spec/enabled` marker, and adds the `@`-import line to the
    repo `CLAUDE.md`. Disabling removes the import line and the marker and
    leaves the rest of `.punt-labs/z-spec/` dormant. Enabling is idempotent and
    is also the upgrade path. Neither runs git: commit the marker in a PR.

    Args:
        action: "enable" or "disable".
        directory: Directory inside the repository. Defaults to the cwd.

    Returns:
        JSON with ok (bool), action, enabled (bool), and the marker, guide,
        and import_line paths, or error.
    """
    return RepoEnablement.apply(EnablementAction(action), Path(directory)).to_json()


@mcp.tool()
@_GATE.guard
def save_audit_report(file: str, report_json: str) -> str:
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
