"""``ProjectRoot`` — the user's open project directory for a plugin-launched server.

plugin.json launches the MCP server with ``uv run --directory ${CLAUDE_PLUGIN_ROOT}``,
so the server process cwd is pinned to the plugin checkout — ``Path.cwd()`` names the
plugin repo, not the project the user has open. Claude Code exposes the project root
as ``CLAUDE_PROJECT_DIR``; plugin.json injects it into the server env. Prefer it, and
fall back to ``Path.cwd()`` for the standalone CLI / --no-plugin case, where cwd is
already the user's project.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Self, final

__all__ = ["ProjectRoot"]

logger = logging.getLogger(__name__)

_PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
_PLUGIN_ROOT_ENV = "ZSPEC_PLUGIN_ROOT"


@final
class ProjectRoot:
    """The user's open project directory, resolved once per session."""

    _path: Path
    __slots__ = ("_path",)

    def __new__(cls, path: Path) -> Self:
        self = super().__new__(cls)
        self._path = path
        return self

    @classmethod
    def resolve(cls) -> Self:
        """Resolve the project root from ``CLAUDE_PROJECT_DIR``, else the cwd.

        An absent, relative, or non-existent env value is not a project signal:
        a relative path would resolve against the pinned plugin cwd and name the
        wrong repo, so only an absolute, existing directory is trusted. Otherwise
        the cwd is the user's project (the --no-plugin / standalone CLI case).
        """
        raw = os.environ.get(_PROJECT_DIR_ENV, "")
        candidate = Path(raw)
        if raw and candidate.is_absolute() and candidate.is_dir():
            return cls(candidate)
        cwd = Path.cwd()
        cls._warn_if_plugin_launched(raw, cwd)
        return cls(cwd)

    @staticmethod
    def _warn_if_plugin_launched(raw: str, cwd: Path) -> None:
        """Say so when the fallback fires under the plugin, where it is wrong.

        ``ZSPEC_PLUGIN_ROOT`` is set only by plugin.json, so its presence means
        the cwd is the pinned plugin checkout and this fallback has just named
        z-spec's own repo as the user's project. Loud, never fatal: the
        standalone CLI reaches the same branch legitimately, and a hard failure
        would take the whole tool surface down over one unset variable.
        """
        if not os.environ.get(_PLUGIN_ROOT_ENV):
            return
        logger.warning(
            "%s is %r, not an existing absolute directory — falling back to the "
            "cwd %s, which under the plugin is the z-spec checkout, not your "
            "project. Tools will read the wrong repo.",
            _PROJECT_DIR_ENV,
            raw,
            cwd,
        )

    @property
    def path(self) -> Path:
        """Return the resolved project directory."""
        return self._path
