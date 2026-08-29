"""Discover the working directory's Z specs and display them via a picker."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Protocol, Self, final

from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.commands.show import Display, DisplayError, SpecParser
from punt_zspec.parser import parse_spec
from punt_zspec.types import SpecModel

__all__ = ["PickerCommand", "PickerResult", "PickerSceneBuilder", "SpecDirectory"]

logger = logging.getLogger(__name__)


class PickerSceneBuilder(Protocol):
    """Build an opaque lux scene from the discovered specs and the root searched.

    ``root`` is passed because the frame title is a constant: the tree that was
    searched reaches the screen through the scene or not at all.
    """

    # object return (PY-TS-14): a lux element; the command forwards it uninspected.
    def __call__(
        self, specs: list[tuple[Path, SpecModel]], root: Path, /
    ) -> object: ...


@final
class SpecDirectory:
    """A directory searched for Z specs, and the rule for which .tex files count.

    A recursive ``**/*.tex`` glob picks up files nobody wrote as a spec: those
    under hidden dirs (``.tmp/``, ``.venv/``, ``.git/``, ``.pytest_cache/`` —
    scratch and tooling), ``templates/preamble.tex``, and LaTeX includes with no
    Z blocks. All three are skipped here, so one stray file never fails a search.
    """

    _root: Path
    _parse: SpecParser
    __slots__ = ("_parse", "_root")

    def __new__(cls, root: Path, parse: SpecParser) -> Self:
        self = super().__new__(cls)
        self._root = root
        self._parse = parse
        return self

    def exists(self) -> bool:
        """Return whether the root is a directory at all."""
        return self._root.is_dir()

    def specs(self) -> list[tuple[Path, SpecModel]]:
        """Return each parsable Z spec below the root, in path order.

        ``build_spec_picker`` takes ``(Path, SpecModel)`` tuples — the opposite
        order to ``BrowseCommand``'s ``(SpecModel, Path)``. Path order makes the
        tabs stable between runs.
        """
        found: list[tuple[Path, SpecModel]] = []
        for tex in sorted(self._root.rglob("*.tex")):
            if self._is_template(tex) or self._is_hidden(tex):
                continue
            try:  # PY-EH-5 exception: parse/read is an I/O boundary; skip a bad .tex
                model = self._parse(tex)
            except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as exc:
                logger.debug("skipping unparsable .tex in picker: %s (%s)", tex, exc)
                continue
            if model.blocks:
                found.append((tex, model))
        return found

    @staticmethod
    def _is_template(tex: Path) -> bool:
        """Return whether ``tex`` is a preamble/template rather than a Z spec."""
        return tex.name == "preamble.tex" or "templates" in tex.parts

    def _is_hidden(self, tex: Path) -> bool:
        """Return whether ``tex`` sits under a hidden dir below the root.

        Only ancestors below the root are checked, so explicitly searching a
        hidden directory still lists its specs.
        """
        return any(
            part.startswith(".") for part in tex.relative_to(self._root).parent.parts
        )


@final
@dataclass(frozen=True, slots=True)
class PickerResult:
    """The count and scene id of a rendered spec picker."""

    total: int
    scene_id: str

    def to_dict(self) -> dict[str, Any]:  # PY-TS-14: JSON wire boundary
        return {"ok": True, "total": self.total, "scene_id": self.scene_id}


@final
class PickerCommand:
    """Discover a directory's Z specs, build the picker scene, and render it.

    The Browse menu callback and the ``pick`` tool/verb both run this command;
    it mirrors ``ShowCommand``/``BrowseCommand`` (PL-PA-3) — injected builder and
    ``Display``, returning a typed ``CommandResult``.

    ``FRAME_TITLE`` is the one name this frame carries on every surface, and the
    name the Browse menu entry registers under: a click must land in a window
    that answers to its label. A constant, not a parameter, so none can differ.
    """

    FRAME_TITLE: ClassVar[str] = "Z-Spec Browser"

    _build: PickerSceneBuilder
    _display: Display
    _parse: SpecParser
    __slots__ = ("_build", "_display", "_parse")

    def __new__(
        cls,
        build: PickerSceneBuilder,
        display: Display,
        parse: SpecParser = parse_spec,
    ) -> Self:
        self = super().__new__(cls)
        self._build = build
        self._display = display
        self._parse = parse
        return self

    def run(
        self, directory: Path, *, frame_id: str = "z-spec-picker"
    ) -> CommandResult[PickerResult]:
        """Render the directory's Z specs into ``frame_id``, or a typed failure.

        ``frame_id`` is the Hub scene id, so the Browse callback raises and
        renders into the same id (ADR §5.2). An absent directory or a directory
        with no Z specs is a ``spec_not_found`` failure; a down display is a
        ``display_failed`` — the same error contract as ``BrowseCommand``.
        """
        # Resolved once: the CLI default ``Path()`` and the MCP default "." are
        # both the cwd, and a scene saying it searched "." has told nobody
        # anything. The failures below keep naming ``directory`` as typed.
        root = directory.resolve()
        search = SpecDirectory(root, self._parse)
        if not search.exists():
            return CommandResult[PickerResult].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"Not a directory: {directory}"
                )
            )
        specs = search.specs()
        if not specs:
            return CommandResult[PickerResult].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"No Z specs found in {directory}"
                )
            )
        try:  # PY-EH-5 exception: report load / scene build is an I/O boundary
            scene = self._build(specs, root)
        except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as exc:
            return CommandResult[PickerResult].failed(
                CommandError(CommandFailure.spec_unreadable, str(exc))
            )
        try:  # PY-EH-5 exception: lux render is an I/O boundary
            self._display.show(scene, frame_id=frame_id, frame_title=self.FRAME_TITLE)
        except DisplayError as exc:
            return CommandResult[PickerResult].failed(
                CommandError(CommandFailure.display_failed, str(exc))
            )
        return CommandResult.ok(PickerResult(total=len(specs), scene_id=frame_id))
