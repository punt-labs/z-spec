"""What an ``enable`` or ``disable`` run did to one repository."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, final

__all__ = ["EnablementAction", "EnablementReport"]


class EnablementAction(StrEnum):
    """The two enablement verbs.

    punt-kit ``tool-enable-disable.md`` §2.3: the vocabulary is ``enable`` /
    ``disable``. A boolean ``y|n`` toggle is not permitted and there is no third
    state — ``enable`` writes the marker, ``disable`` removes it.
    """

    enable = "enable"
    disable = "disable"


@final
@dataclass(frozen=True, slots=True)
class EnablementReport:
    """The repo's enablement state after the verb ran, for either surface."""

    action: EnablementAction
    root: Path
    marker: Path
    guide: Path
    import_line: str
    enabled: bool

    def to_dict(self) -> dict[str, Any]:  # PY-TS-14: JSON wire boundary
        return {
            "ok": True,
            "action": str(self.action),
            "enabled": self.enabled,
            "root": str(self.root),
            "marker": str(self.marker),
            "guide": str(self.guide),
            "import_line": self.import_line,
        }

    def render(self) -> str:
        """Return the human-readable block the CLI prints.

        The report owns both its forms, so the terminal and the wire cannot
        drift. Neither surface runs git, hence the closing reminder: what
        enablement produced is a working-tree change the user still commits.
        """
        return "\n".join(
            (
                f"z-spec {'enabled' if self.enabled else 'disabled'} in {self.root}",
                f"  marker: {self.marker}",
                f"  guide:  {self.guide}",
                f"  import: {self.import_line}",
                "Commit the marker so enablement travels with the repo."
                if self.enabled
                else "Commit its removal so the repo stays off for everyone.",
            )
        )
