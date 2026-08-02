"""Discover the working directory's Z specs and display them via a picker."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, final

from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.commands.show import Display, DisplayError, SpecParser
from punt_zspec.parser import parse_spec
from punt_zspec.types import SpecModel

logger = logging.getLogger(__name__)


class PickerSceneBuilder(Protocol):
    """Build an opaque lux scene from the discovered (path, model) specs.

    ``root`` is the discovery directory the specs were globbed from; the builder
    labels each tab by its spec's path relative to ``root``.
    """

    # object return (PY-TS-14): a lux element; the command forwards it uninspected.
    def __call__(
        self, specs: list[tuple[Path, SpecModel]], root: Path, /
    ) -> object: ...


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
    """

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
        if not directory.is_dir():
            return CommandResult[PickerResult].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"Not a directory: {directory}"
                )
            )
        specs = self._discover(directory)
        if not specs:
            return CommandResult[PickerResult].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"No Z specs found in {directory}"
                )
            )
        try:  # PY-EH-5 exception: report load / scene build is an I/O boundary
            scene = self._build(specs, directory)
        except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as exc:
            return CommandResult[PickerResult].failed(
                CommandError(CommandFailure.spec_unreadable, str(exc))
            )
        try:  # PY-EH-5 exception: lux render is an I/O boundary
            self._display.show(
                scene, frame_id=frame_id, frame_title=f"Z Specs: {directory.name}"
            )
        except DisplayError as exc:
            return CommandResult[PickerResult].failed(
                CommandError(CommandFailure.display_failed, str(exc))
            )
        return CommandResult.ok(PickerResult(total=len(specs), scene_id=frame_id))

    def _discover(self, directory: Path) -> list[tuple[Path, SpecModel]]:
        """Return each parsable, non-template Z spec under ``directory``.

        ``build_spec_picker`` takes ``(Path, SpecModel)`` tuples — the opposite
        order to ``BrowseCommand``'s ``(SpecModel, Path)``. A cwd ``**/*.tex``
        glob also picks up ``templates/preamble.tex`` and LaTeX includes carrying
        no Z blocks; both are skipped so one stray include never fails the whole
        picker. Specs are ordered by path for stable tabs.
        """
        specs: list[tuple[Path, SpecModel]] = []
        for tex in sorted(directory.rglob("*.tex")):
            if self._is_template(tex):
                continue
            try:  # PY-EH-5 exception: parse/read is an I/O boundary; skip a bad .tex
                model = self._parse(tex)
            except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError) as exc:
                logger.debug("skipping unparsable .tex in picker: %s (%s)", tex, exc)
                continue
            if model.blocks:
                specs.append((tex, model))
        return specs

    @staticmethod
    def _is_template(tex: Path) -> bool:
        """Return whether ``tex`` is a preamble/template rather than a Z spec."""
        return tex.name == "preamble.tex" or "templates" in tex.parts
