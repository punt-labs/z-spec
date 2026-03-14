"""FastMCP server for punt-zspec."""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from punt_zspec import __version__

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "zspec",
    instructions=(
        "Z specification toolkit. Use these tools to type-check Z specs "
        "with fuzz, model-check with probcli, and display specs in lux."
    ),
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
    if _client is None:
        return
    try:
        from punt_lux.protocol import TextElement

        _client.show_async(
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
    if _client is None:
        logger.error("Tutorial callback fired but _client is None")
        return
    manifest = _tutorial_manifest()
    if manifest is None:
        logger.warning("Tutorial manifest not found")
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
        _client.show_async(
            "z-spec-browser",
            [scene],
            frame_id="z-spec-browser",
            frame_title=collection.title,
        )
    except Exception as exc:
        logger.exception("Failed to open tutorial")
        _show_error(
            "z-spec-browser", "Tutorial Error", f"Failed to open tutorial: {exc}"
        )


def _on_spec_browser_click(_msg: Any) -> None:
    """Menu callback: open the spec browser with discovered .tex files."""
    if _client is None:
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
        _client.show_async(
            "z-spec-picker",
            [scene],
            frame_id="z-spec-picker",
            frame_title="Z Spec Browser",
        )
    except Exception:
        logger.exception("Failed to open spec browser")


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


def _with_lux(fn: Any) -> dict[str, Any]:
    """Run fn(client) with auto-reconnect on socket failure."""
    global _client, _apps_registered_for
    with _client_lock:
        try:
            return fn(_get_client())  # type: ignore[no-any-return]
        except (ConnectionError, OSError):
            if _client is not None:
                try:
                    _client.close()
                except Exception:
                    logger.debug(
                        "Error closing client before reconnect",
                        exc_info=True,
                    )
                _client = None
                _apps_registered_for = None
            try:
                return fn(_get_client())  # type: ignore[no-any-return]
            except (ConnectionError, OSError) as exc:
                logger.warning("Lux reconnect failed: %s", exc)
                return {"status": "error", "message": str(exc)}


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


def _validate_spec_path(file: str) -> Path | None:
    """Validate a spec file path. Returns Path if valid, None if not."""
    path = Path(file)
    if not path.exists() or not path.is_file():
        return None
    return path


@mcp.tool()
def check(file: str) -> str:
    """Type-check a Z specification with fuzz.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON with ok (bool) and errors (list).
    """
    from punt_zspec.fuzz import resolve_fuzz, run_fuzz
    from punt_zspec.report import save_fuzz

    path = _validate_spec_path(file)
    if path is None:
        return json.dumps({"ok": False, "error": f"Spec file not found: {file}"})
    binary = resolve_fuzz()
    if binary is None:
        return json.dumps({"ok": False, "error": "fuzz not found"})
    result = run_fuzz(path, binary)
    save_fuzz(path, result)
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

    path = _validate_spec_path(file)
    if path is None:
        return json.dumps({"ok": False, "error": f"Spec file not found: {file}"})
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

    path = _validate_spec_path(file)
    if path is None:
        return json.dumps({"ok": False, "error": f"Spec file not found: {file}"})
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

    path = _validate_spec_path(file)
    if path is None:
        return json.dumps({"ok": False, "error": f"Spec file not found: {file}"})
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
    """Parse a Z spec and display it in lux.

    Loads all available reports (fuzz, ProB, partition, audit) and
    renders each as a tab alongside the Spec tab.

    Args:
        file: Path to the .tex Z specification file.

    Returns:
        JSON with status ("displayed" or "error").
    """
    from punt_zspec.applet import build_z_spec_scene
    from punt_zspec.parser import parse_spec
    from punt_zspec.report import (
        load_audit,
        load_fuzz,
        load_partition,
        load_report,
    )

    path = _validate_spec_path(file)
    if path is None:
        return json.dumps({"ok": False, "error": f"Spec file not found: {file}"})

    try:
        spec = parse_spec(path)
        scene = build_z_spec_scene(
            path,
            spec,
            report=load_report(path),
            fuzz=load_fuzz(path),
            partition=load_partition(path),
            audit=load_audit(path),
        )
    except (
        FileNotFoundError,
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        return json.dumps({"ok": False, "error": f"Failed to read spec: {exc}"})

    def _show(client: Any) -> dict[str, Any]:
        client.show(
            "z-spec",
            [scene],
            frame_id="z-spec",
            frame_title=f"Z-Spec: {path.name}",
        )
        return {"status": "displayed", "scene_id": "z-spec"}

    return json.dumps(_with_lux(_show))


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


@mcp.tool()
def save_partition_report(file: str, report_json: str) -> str:
    """Validate and save a partition report for a Z specification.

    Called by the /z-spec:partition skill after generating partitions.
    The report is saved as <stem>.partition.json alongside the .tex file.

    Args:
        file: Path to the .tex Z specification file.
        report_json: JSON string matching the partition report schema.

    Returns:
        JSON with ok (bool) and path to saved report.
    """
    from punt_zspec.report import partition_from_dict, save_partition

    path = _validate_spec_path(file)
    if path is None:
        return json.dumps({"ok": False, "error": f"Spec file not found: {file}"})

    try:
        data = json.loads(report_json)
        report = partition_from_dict(data)
        out = save_partition(path, report)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return json.dumps({"ok": False, "error": f"Invalid partition report: {exc}"})
    return json.dumps({"ok": True, "path": str(out)})


@mcp.tool()
def browse(manifest: str) -> str:
    """Open a Z spec collection in the tutorial browser.

    Parses a manifest.toml and displays all lessons in a paged lux view.
    Navigation is instant and client-side — no round-trips.

    Args:
        manifest: Path to the manifest.toml file.

    Returns:
        JSON with status, total lessons, and collection title.
    """
    from punt_zspec.browser import build_browser_scene
    from punt_zspec.manifest import parse_manifest
    from punt_zspec.parser import parse_spec
    from punt_zspec.types import SpecModel

    path = Path(manifest)
    if not path.exists():
        return json.dumps(
            {"status": "error", "error": f"Manifest not found: {manifest}"}
        )

    try:
        collection = parse_manifest(path)
        browse_specs: list[tuple[SpecModel, Path]] = []
        for lesson in collection.lessons:
            tex_path = collection.base_path / lesson.spec_path
            if not tex_path.exists():
                return json.dumps(
                    {
                        "status": "error",
                        "error": f"Spec not found: {tex_path}",
                    }
                )
            browse_specs.append((parse_spec(tex_path), tex_path))
        scene = build_browser_scene(collection, browse_specs)

        def _show(client: Any) -> dict[str, Any]:
            client.show(
                "z-spec-browser",
                [scene],
                frame_id="z-spec-browser",
                frame_title=collection.title,
            )
            return {
                "status": "displayed",
                "total": len(collection.lessons),
                "title": collection.title,
            }

        return json.dumps(_with_lux(_show))
    except (FileNotFoundError, ValueError) as exc:
        return json.dumps({"status": "error", "error": str(exc)})


@mcp.tool()
def save_audit_report(file: str, report_json: str) -> str:
    """Validate and save an audit report for a Z specification.

    Called by the /z-spec:audit skill after auditing test coverage.
    The report is saved as <stem>.audit.json alongside the .tex file.

    Args:
        file: Path to the .tex Z specification file.
        report_json: JSON string matching the audit report schema.

    Returns:
        JSON with ok (bool) and path to saved report.
    """
    from punt_zspec.report import audit_from_dict, save_audit

    path = _validate_spec_path(file)
    if path is None:
        return json.dumps({"ok": False, "error": f"Spec file not found: {file}"})

    try:
        data = json.loads(report_json)
        report = audit_from_dict(data)
        out = save_audit(path, report)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        return json.dumps({"ok": False, "error": f"Invalid audit report: {exc}"})
    return json.dumps({"ok": True, "path": str(out)})
