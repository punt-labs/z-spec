"""Per-repo enablement: the one definition of ``enable`` and ``disable``.

Both surfaces route here — the ``z-spec enable`` / ``z-spec disable`` CLI verbs
and the ``enable`` / ``disable`` MCP tools — so a marker written by one is
identical to one written by the other (punt-kit ``tool-enable-disable.md``
§2.14).

The state machine has three presence facts: the tool-owned
``.punt-labs/z-spec/`` directory, the ``enabled`` marker inside it (§2.7), and
the canonical ``@.punt-labs/z-spec/CLAUDE.md`` import in the repo ``CLAUDE.md``
(§2.4). Every transition preserves the §2.11 biconditional — the marker is
present exactly when the import line is.

There is no fourth fact: z-spec ships its one hook through the marketplace
plugin, which is global, so ``enable`` computes an empty §2.8 entry set and
touches no ``<repo>/.claude/settings.json``. An empty registration would be a
no-op write on a file shared with every other tool.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Self, final

from punt_zspec.claude_md import ClaudeMdImport
from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.types import EnablementAction, EnablementReport

__all__ = ["DepositedGuide", "EnabledMarker", "RepoEnablement"]

# The exact canonical repo-scope import line (§2.4): byte-identical across all
# punt CLIs, what enable writes, what disable prunes, what punt audit greps.
IMPORT_LINE = "@.punt-labs/z-spec/CLAUDE.md"

_SUBTREE = (".punt-labs", "z-spec")
_GUIDE_ASSET = "assets/enablement-guide.md"


@final
class EnabledMarker:
    """The committed on-signal ``.punt-labs/z-spec/enabled`` (§2.7).

    Presence of the *directory* cannot mean enabled — it persists, dormant,
    after ``disable`` — so the marker is a separate file, and it is git-tracked:
    enablement is per-repo policy reviewed in a PR, not a per-user preference.
    """

    _path: Path
    __slots__ = ("_path",)

    def __new__(cls, path: Path) -> Self:
        self = super().__new__(cls)
        self._path = path
        return self

    @property
    def path(self) -> Path:
        """Return the marker path."""
        return self._path

    def is_present(self) -> bool:
        """Return whether the marker is a regular file.

        A symlink is not the signal: a committed symlink at the marker path
        could otherwise redirect the enablement decision outside the repo.
        """
        return self._path.is_file() and not self._path.is_symlink()

    def write(self) -> None:
        """Create the empty marker file, replacing a symlink squatting on it."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        if self._path.is_symlink():
            self._path.unlink()
        self._path.touch()

    def remove(self) -> None:
        """Delete the marker if present. Idempotent."""
        self._path.unlink(missing_ok=True)


@final
class DepositedGuide:
    """z-spec's static user guide, deposited at ``.punt-labs/z-spec/CLAUDE.md``.

    §2.5: the guide is static content shipped with the tool — the same bytes
    everywhere, no per-repo rendering. §2.2: the vendored zone is overwritten
    wholesale on every ``enable``, never read-modify-merged, so the same tool
    version always produces the same file.
    """

    _path: Path
    __slots__ = ("_path",)

    def __new__(cls, path: Path) -> Self:
        self = super().__new__(cls)
        self._path = path
        return self

    @property
    def path(self) -> Path:
        """Return the deposited guide's path."""
        return self._path

    def deposit(self) -> None:
        """Write the shipped guide over whatever is there."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(self.content(), encoding="utf-8")

    @staticmethod
    def content() -> str:
        """Return the guide shipped inside the package."""
        return files("punt_zspec").joinpath(_GUIDE_ASSET).read_text(encoding="utf-8")


@final
class RepoEnablement:
    """Turn z-spec on and off in one repository.

    The single source of truth for what the two verbs do, so the CLI and the
    MCP tools stay equivalent. Neither runs git: the marker and the deposited
    guide are working-tree changes the user commits in a PR like any other.
    """

    _guide: DepositedGuide
    _marker: EnabledMarker
    _import: ClaudeMdImport
    __slots__ = ("_guide", "_import", "_marker")

    def __new__(
        cls, *, guide: DepositedGuide, marker: EnabledMarker, claude_md: ClaudeMdImport
    ) -> Self:
        self = super().__new__(cls)
        self._guide = guide
        self._marker = marker
        self._import = claude_md
        return self

    @classmethod
    def for_repo(cls, root: Path) -> Self:
        """Wire the real per-repo paths under *root*."""
        subtree = root.joinpath(*_SUBTREE)
        return cls(
            guide=DepositedGuide(subtree / "CLAUDE.md"),
            marker=EnabledMarker(subtree / "enabled"),
            claude_md=ClaudeMdImport(root / "CLAUDE.md", IMPORT_LINE),
        )

    @classmethod
    def for_directory(cls, start: Path) -> Self:
        """Wire the repository containing *start*.

        Raises ``ValueError`` when *start* is not inside a git repository:
        ``enable`` and ``disable`` are repo-scoped verbs (§2.3), so a non-repo
        invocation is a clean boundary failure, never a silent no-op.
        """
        return cls.for_repo(cls.find_root(start))

    @staticmethod
    def find_root(start: Path) -> Path:
        """Return the git repository root at or above *start*, or raise.

        A ``.git`` entry may be a directory or, in a worktree or submodule, a
        file — both mark the root.
        """
        current = start.resolve()
        for candidate in (current, *current.parents):
            if (candidate / ".git").exists():
                return candidate
        msg = f"not inside a git repository: {start}"
        raise ValueError(msg)

    @property
    def marker_path(self) -> Path:
        """Return the ``enabled`` marker path."""
        return self._marker.path

    @property
    def guide_path(self) -> Path:
        """Return the deposited guide's path."""
        return self._guide.path

    @property
    def import_line(self) -> str:
        """Return the canonical ``@``-import line enablement owns."""
        return self._import.line

    @property
    def root(self) -> Path:
        """Return the repository root this instance operates on."""
        return self._marker.path.parents[len(_SUBTREE)]

    @classmethod
    def apply(
        cls, action: EnablementAction, directory: Path
    ) -> CommandResult[EnablementReport]:
        """Run *action* on the repository containing *directory*, and report.

        The one entry point both verb commands call, so a marker written by
        ``z-spec enable`` and one written by the MCP tool are identical (§2.14).
        """
        try:
            enablement = cls.for_directory(directory)
        except ValueError as exc:
            return CommandResult[EnablementReport].failed(
                CommandError(
                    kind=CommandFailure.not_a_repository,
                    message=str(exc),
                    hint="Run it from inside the repository you want to change.",
                )
            )
        try:  # PY-EH-5 exception: the repo working tree is an I/O boundary
            report = enablement.perform(action)
        except OSError as exc:
            # A read-only CLAUDE.md, a `.punt-labs` that is a regular file, an
            # undeletable marker, or a wheel shipped without the guide asset —
            # each is the user's repo refusing the write, not a z-spec bug, so
            # it renders as a failure both surfaces already know how to print.
            return CommandResult[EnablementReport].failed(
                CommandError(
                    kind=CommandFailure.enablement_failed,
                    message=f"Failed to {action} z-spec: {exc}",
                    hint="Check the repository is writable, then run it again.",
                )
            )
        return CommandResult.ok(report)

    def perform(self, action: EnablementAction) -> EnablementReport:
        """Reach the state *action* names, then report what is on disk."""
        if action is EnablementAction.enable:
            self.enable()
        else:
            self.disable()
        return EnablementReport(
            action=action,
            root=self.root,
            marker=self.marker_path,
            guide=self.guide_path,
            import_line=self.import_line,
            enabled=self.is_enabled(),
        )

    def is_enabled(self) -> bool:
        """Return whether z-spec is enabled here (the marker is present)."""
        return self._marker.is_present()

    def enable(self) -> None:
        """Reach the enabled state from anywhere; idempotent, and the upgrade path.

        Order is crash-safety, not taste (§2.3): the guide first, so the import
        never points at a missing file; then the import line; the marker
        **last**, because the marker is what the MCP gate reads. If any earlier
        step raises, the repo is left observably off rather than half on.
        """
        self._guide.deposit()
        self._import.register()
        self._marker.write()

    def disable(self) -> None:
        """Reach the dormant state non-destructively (§2.9).

        The import goes first, so the biconditional holds the moment the marker
        does. The rest of ``.punt-labs/z-spec/`` is left exactly as found —
        ``disable`` stops composition, it does not erase committed content.
        """
        self._import.prune()
        self._marker.remove()
