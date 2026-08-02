"""The ``disable`` verb."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from punt_zspec.commands.enablement import RepoEnablement
from punt_zspec.types import EnablementAction

if TYPE_CHECKING:
    from pathlib import Path

    from punt_zspec.commands.result import CommandResult
    from punt_zspec.types import EnablementReport


@final
class DisableCommand:
    """Turn z-spec off in one repository (punt-kit ``tool-enable-disable.md`` §2.3).

    Non-destructive (§2.9): the import line goes and the marker goes, but the
    rest of ``.punt-labs/z-spec/`` stays exactly as found, dormant. Only an
    explicit purge may delete deposited content, and z-spec ships no purge.
    """

    __slots__ = ()

    def run(self, directory: Path) -> CommandResult[EnablementReport]:
        """Disable z-spec in the repository containing *directory*.

        Idempotent on a repo that was never enabled: both removals are no-ops
        and the report records the off state.
        """
        return RepoEnablement.apply(EnablementAction.disable, directory)
