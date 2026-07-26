"""Render a Z spec and its reports through an injected display surface."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, final

from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.parser import parse_spec
from punt_zspec.report import load_all_reports
from punt_zspec.types import SpecModel, SpecReports


class Display(Protocol):
    """Render an opaque scene. Raises DisplayError when the surface is down."""

    # object (PY-TS-14): the scene is a lux element built by an injected builder;
    # the command forwards it uninspected to keep punt_lux out of this layer.
    def show(self, scene: object, *, frame_id: str, frame_title: str) -> None: ...


class DisplayError(Exception):
    """The display surface could not render — an expected, recoverable failure."""


class SpecParser(Protocol):
    """Parse a .tex spec into a SpecModel, raising on unreadable input."""

    def __call__(self, path: Path, /) -> SpecModel: ...


class SpecReportsLoader(Protocol):
    """Load the four persisted reports beside a spec into one bundle."""

    def __call__(self, spec: Path, /) -> SpecReports: ...


class SpecSceneBuilder(Protocol):
    """Build an opaque lux scene from a spec, its model, and its reports."""

    # object return (PY-TS-14): a lux element; the command forwards it uninspected.
    def __call__(
        self, spec: Path, model: SpecModel, reports: SpecReports, /
    ) -> object: ...


@final
@dataclass(frozen=True, slots=True)
class DisplayResult:
    """The identifier of the rendered scene."""

    scene_id: str

    def to_dict(self) -> dict[str, Any]:  # PY-TS-14: JSON wire boundary
        return {"ok": True, "scene_id": self.scene_id}


@final
class ShowCommand:
    """Parse a spec, build its scene, and render it on the injected display."""

    _build: SpecSceneBuilder
    _display: Display
    _parse: SpecParser
    _load: SpecReportsLoader
    __slots__ = ("_build", "_display", "_load", "_parse")

    def __new__(
        cls,
        build: SpecSceneBuilder,
        display: Display,
        parse: SpecParser = parse_spec,
        load: SpecReportsLoader = load_all_reports,
    ) -> Self:
        self = super().__new__(cls)
        self._build = build
        self._display = display
        self._parse = parse
        self._load = load
        return self

    def run(self, spec: Path) -> CommandResult[DisplayResult]:
        """Render the spec, or return a typed failure."""
        if not spec.is_file():
            return CommandResult[DisplayResult].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"Spec file not found: {spec}"
                )
            )
        try:  # PY-EH-5 exception: parse/read is an I/O boundary
            model = self._parse(spec)
            scene = self._build(spec, model, self._load(spec))
        except (
            FileNotFoundError,
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as exc:
            return CommandResult[DisplayResult].failed(
                CommandError(
                    CommandFailure.spec_unreadable, f"Failed to read spec: {exc}"
                )
            )
        try:  # PY-EH-5 exception: lux render is an I/O boundary
            self._display.show(
                scene, frame_id="z-spec", frame_title=f"Z-Spec: {spec.name}"
            )
        except DisplayError as exc:
            return CommandResult[DisplayResult].failed(
                CommandError(CommandFailure.display_failed, str(exc))
            )
        return CommandResult.ok(DisplayResult(scene_id="z-spec"))
