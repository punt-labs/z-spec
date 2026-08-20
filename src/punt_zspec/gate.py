"""The enablement gate: whether the MCP tool surface answers here."""

from __future__ import annotations

import json
from functools import wraps
from typing import TYPE_CHECKING, Self, final

from punt_zspec.commands.enablement import RepoEnablement
from punt_zspec.commands.result import CommandError, CommandFailure

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

__all__ = ["EnablementGate"]

# The refusal every gated tool answers with. It names the enable command,
# because the model reading the result is the one who must offer the fix. The
# message carries only that; the panel channel budgets 80 columns for
# "<tool>: error — <message>", and the remaining detail lives in the hint.
_DECLINED = CommandError(
    kind=CommandFailure.not_enabled,
    message="z-spec is not enabled here. Run `z-spec enable` or /z-spec:enable.",
    hint="Then commit .punt-labs/z-spec/enabled so the repo stays on.",
)


@final
class EnablementGate:
    """Gate the MCP tool surface on the repo's ``enabled`` marker (§2.3).

    This is the only gate. The lux menu registration lives in the server's
    FastMCP lifespan and the sole entry in ``plugin/hooks/hooks.json`` matches
    ``mcp__…zspec__.*``, so both are downstream of the server: gating it gates
    them. The CLI is deliberately *not* gated — a shell invocation is explicit
    by definition, and the standard governs plugin presence.

    The marker is read on every call, never cached, so ``enable`` takes effect
    on the next tool call rather than on the next server restart.
    """

    _directory: Path
    __slots__ = ("_directory",)

    def __new__(cls, directory: Path) -> Self:
        self = super().__new__(cls)
        self._directory = directory
        return self

    def is_open(self) -> bool:
        """Return whether z-spec is enabled where the server is running.

        Outside a git repository there is no marker to read and no repo policy
        to honour, so the surface stays shut — the §2.3 graceful no-op, never
        a trigger to self-enable.
        """
        try:
            return RepoEnablement.for_directory(self._directory).is_enabled()
        except ValueError:
            return False

    def decline(self) -> str:
        """Return the JSON refusal, naming the command that turns z-spec on."""
        return json.dumps(_DECLINED.to_dict())

    def guard[**P](self, tool: Callable[P, str]) -> Callable[P, str]:
        """Return *tool* wrapped so it declines wherever the marker is absent.

        Applied under ``@mcp.tool()`` so FastMCP registers the guarded
        callable; ``wraps`` keeps the name, docstring, and signature FastMCP
        derives the tool schema from.
        """

        @wraps(tool)
        def gated(*args: P.args, **kwargs: P.kwargs) -> str:
            return tool(*args, **kwargs) if self.is_open() else self.decline()

        return gated
