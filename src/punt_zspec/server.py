"""FastMCP server for punt-zspec."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mcp.server.fastmcp import FastMCP

from punt_zspec import __version__

if TYPE_CHECKING:
    from punt_zspec.types import Collection, SpecModel, SpecReports

logger = logging.getLogger(__name__)


@contextlib.asynccontextmanager
async def _lifespan(_server: FastMCP) -> AsyncIterator[None]:
    """Eagerly connect to Lux and register menu items at server startup."""
    try:
        await asyncio.to_thread(_eager_lux_connect)
    except (ConnectionError, OSError):
        logger.debug(
            "Lux not reachable at startup; will connect on first tool call",
            exc_info=True,
        )
    except ImportError:
        logger.warning("punt_lux not installed; Lux features disabled")
    except Exception:
        logger.warning(
            "Unexpected error during eager Lux connect",
            exc_info=True,
        )
    yield


def _eager_lux_connect() -> None:
    """Synchronous helper: connect to Lux and register menu items."""
    with _client_lock:
        _get_client()


mcp = FastMCP(
    "zspec",
    instructions=(
        "Z specification toolkit. Use these tools to type-check Z specs "
        "with fuzz, model-check with probcli, and display specs in lux."
    ),
    lifespan=_lifespan,
)
if hasattr(mcp, "_mcp_server") and hasattr(mcp._mcp_server, "version"):  # pyright: ignore[reportPrivateUsage]
    mcp._mcp_server.version = __version__  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------
# Persistent LuxClient for menu registration
# ---------------------------------------------------------------------------

_client: Any = None
_apps_registered_for: int | None = None
_client_lock = threading.Lock()


def _plugin_root() -> Path | None:
    """Resolve the plugin root directory."""
    env = os.environ.get("ZSPEC_PLUGIN_ROOT")
    if env:
        p = Path(env)
        if p.is_dir():
            return p
    # Fallback for editable installs: src/punt_zspec/ → ../../
    pkg = Path(__file__).resolve().parent
    candidate = pkg.parent.parent
    if (candidate / "tutorials").is_dir():
        return candidate
    return None


def _tutorial_manifest() -> Path | None:
    """Return the path to the shipped tutorial manifest, if it exists."""
    root = _plugin_root()
    if root is None:
        return None
    manifest = root / "tutorials" / "intro" / "manifest.toml"
    return manifest if manifest.exists() else None


def _show_error(frame_id: str, title: str, message: str) -> None:
    """Show an error message in a lux frame. Best-effort, never raises."""
    client = _client
    if client is None:
        return
    try:
        from punt_lux.protocol import TextElement

        client.show_async(
            frame_id,
            [TextElement(id="error", content=message)],
            frame_id=frame_id,
            frame_title=title,
            frame_size=(500, 80),
        )
    except Exception:
        logger.debug("Failed to show error in lux", exc_info=True)


def _on_tutorial_click(_msg: Any) -> None:
    """Menu callback: open the tutorial browser."""
    client = _client  # capture local reference to avoid race with reconnect
    if client is None:
        logger.error("Tutorial callback fired but _client is None")
        return
    manifest = _tutorial_manifest()
    if manifest is None:
        logger.warning("Tutorial manifest not found")
        _show_error(
            "z-spec-browser",
            "Tutorial Error",
            "Tutorial manifest not found. Reinstall the z-spec plugin.",
        )
        return
    from punt_zspec.browser import build_browser_scene
    from punt_zspec.manifest import parse_manifest
    from punt_zspec.parser import parse_spec

    try:
        collection = parse_manifest(manifest)
        tut_specs: list[tuple[Any, Path]] = []
        for lesson in collection.lessons:
            tex_path = collection.base_path / lesson.spec_path
            if not tex_path.exists():
                _show_error(
                    "z-spec-browser",
                    "Tutorial Error",
                    f"Lesson spec not found: {tex_path}",
                )
                return
            tut_specs.append((parse_spec(tex_path), tex_path))
        scene = build_browser_scene(collection, tut_specs)
        client.show_async(
            "z-spec-browser",
            [scene],
            frame_id="z-spec-browser",
            frame_title=collection.title,
        )
    except Exception as exc:
        logger.exception("Failed to open tutorial")
        _show_error(
            "z-spec-browser",
            "Tutorial Error",
            f"Failed to open tutorial: {exc}",
        )


def _on_spec_browser_click(_msg: Any) -> None:
    """Menu callback: open the spec browser with discovered .tex files."""
    client = _client  # capture local reference to avoid race with reconnect
    if client is None:
        logger.error("Spec browser callback fired but _client is None")
        return

    try:
        from punt_zspec.browser import build_spec_picker
        from punt_zspec.parser import parse_spec

        cwd = Path.cwd()
        tex_files = sorted(
            p
            for p in cwd.rglob("*.tex")
            if not any(part.startswith(".") for part in p.relative_to(cwd).parts)
        )
        specs: list[tuple[Path, Any]] = []
        for tex in tex_files:
            try:
                content = tex.read_text(encoding="utf-8", errors="ignore")
                if "\\begin{schema}" in content or "\\begin{zed}" in content:
                    specs.append((tex, parse_spec(tex)))
            except (ValueError, SyntaxError) as exc:
                logger.warning("Skipped %s: %s", tex, exc)
            except Exception:
                logger.exception("Unexpected error loading %s", tex)

        if not specs:
            _show_error(
                "z-spec-picker",
                "Z Spec Browser",
                "No Z specifications found in this project.",
            )
            return

        scene = build_spec_picker(specs)
        client.show_async(
            "z-spec-picker",
            [scene],
            frame_id="z-spec-picker",
            frame_title="Z Spec Browser",
        )
    except Exception as exc:
        logger.exception("Failed to open spec browser")
        _show_error(
            "z-spec-picker",
            "Z Spec Browser Error",
            f"Failed to open spec browser: {exc}",
        )


def _setup_apps(client: Any) -> None:
    """Register application menu items. Idempotent per client instance."""
    global _apps_registered_for
    if _apps_registered_for == id(client):
        return

    # Tutorial — always registered if manifest exists
    if _tutorial_manifest() is not None:
        client.declare_menu_item(
            {"id": "zspec-tutorial", "label": "Z Notation Tutorial"}
        )
        client.on_event("zspec-tutorial", "menu", _on_tutorial_click)

    # Spec browser — always registered
    client.declare_menu_item({"id": "zspec-browser", "label": "Z Spec Browser"})
    client.on_event("zspec-browser", "menu", _on_spec_browser_click)

    _apps_registered_for = id(client)


def _get_client() -> Any:
    """Return a connected LuxClient with menu items registered.

    Caller must hold _client_lock.
    """
    global _client
    from punt_lux.client import LuxClient

    if _client is None:
        _client = LuxClient(name="z-spec")
    _setup_apps(_client)
    if not _client.is_connected:
        _client.connect()
    if not _client.listener_active:
        _client.start_listener()
    return _client


def _get_client_locked() -> Any:
    """Return the shared menu client, connecting under the client lock."""
    with _client_lock:
        return _get_client()


def _reset_client_locked() -> None:
    """Drop the shared menu client so the next connect rebuilds it."""
    global _client, _apps_registered_for
    with _client_lock:
        if _client is not None:
            try:
                _client.close()
            except Exception:
                logger.debug("Error closing client before reconnect", exc_info=True)
            _client = None
            _apps_registered_for = None


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
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
def doctor() -> str:
    """Report Z-toolkit environment health.

    Returns:
        JSON with version, resolved fuzz/probcli paths, and healthy (bool).
    """
    from punt_zspec.commands.doctor import DoctorCommand

    return DoctorCommand().run().to_json()


@mcp.tool()
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

    display = LuxDisplay(provide=_get_client_locked, reset=_reset_client_locked)
    return ShowCommand(build=build, display=display).run(Path(file)).to_json()


@mcp.tool()
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
def browse(manifest: str) -> str:
    """Open a Z spec collection in the tutorial browser.

    Parses a manifest.toml and displays all lessons in a paged lux view.
    Navigation is instant and client-side — no round-trips.

    Args:
        manifest: Path to the manifest.toml file.

    Returns:
        JSON with ok (bool), total lessons, and collection title.
    """
    from punt_zspec.browser import build_browser_scene
    from punt_zspec.commands.browse import BrowseCommand
    from punt_zspec.display import LuxDisplay

    def build(collection: Collection, specs: list[tuple[SpecModel, Path]]) -> object:
        return build_browser_scene(collection, specs)

    display = LuxDisplay(provide=_get_client_locked, reset=_reset_client_locked)
    return BrowseCommand(build=build, display=display).run(Path(manifest)).to_json()


@mcp.tool()
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
