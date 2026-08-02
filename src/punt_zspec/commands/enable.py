"""The ``enable`` verb."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from punt_zspec.commands.enablement import RepoEnablement
from punt_zspec.types import EnablementAction

if TYPE_CHECKING:
    from pathlib import Path

    from punt_zspec.commands.result import CommandResult
    from punt_zspec.types import EnablementReport


@final
class EnableCommand:
    """Turn z-spec on in one repository (punt-kit ``tool-enable-disable.md`` §2.3).

    Idempotent, and re-running is the upgrade path: the guide is redeposited
    wholesale, the import line is added only when absent, and the marker is
    rewritten. Nothing here runs git — the marker is a working-tree change the
    user commits in a PR.
    """

    __slots__ = ()

    def run(self, directory: Path) -> CommandResult[EnablementReport]:
        """Enable z-spec in the repository containing *directory*.

        Fails only when *directory* is outside a git repository, since
        enablement is repo-scoped and has nowhere to write.
        """
        return RepoEnablement.apply(EnablementAction.enable, directory)
