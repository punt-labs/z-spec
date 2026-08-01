"""Open a Z spec collection in the tutorial browser via an injected display."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, final

from punt_zspec.commands.result import CommandError, CommandFailure, CommandResult
from punt_zspec.commands.show import Display, DisplayError, SpecParser
from punt_zspec.manifest import parse_manifest
from punt_zspec.parser import parse_spec
from punt_zspec.types import Collection, SpecModel


class ManifestParser(Protocol):
    """Parse a manifest.toml into a Collection, raising on bad input."""

    def __call__(self, path: Path, /) -> Collection: ...


class BrowseSceneBuilder(Protocol):
    """Build an opaque lux scene from a collection and its parsed specs."""

    # object return (PY-TS-14): a lux element; the command forwards it uninspected.
    def __call__(
        self, collection: Collection, specs: list[tuple[SpecModel, Path]], /
    ) -> object: ...


@final
@dataclass(frozen=True, slots=True)
class BrowseResult:
    """The lesson count and title of a rendered collection."""

    total: int
    title: str

    def to_dict(self) -> dict[str, Any]:  # PY-TS-14: JSON wire boundary
        return {"ok": True, "total": self.total, "title": self.title}


@final
class BrowseCommand:
    """Parse a manifest, build its browser scene, and render it."""

    _build: BrowseSceneBuilder
    _display: Display
    _parse_manifest: ManifestParser
    _parse_spec: SpecParser
    __slots__ = ("_build", "_display", "_parse_manifest", "_parse_spec")

    def __new__(
        cls,
        build: BrowseSceneBuilder,
        display: Display,
        parse_manifest: ManifestParser = parse_manifest,
        parse_spec: SpecParser = parse_spec,
    ) -> Self:
        self = super().__new__(cls)
        self._build = build
        self._display = display
        self._parse_manifest = parse_manifest
        self._parse_spec = parse_spec
        return self

    def run(
        self, manifest: Path, *, frame_id: str = "z-spec-browser"
    ) -> CommandResult[BrowseResult]:
        """Render the collection into ``frame_id``, or return a typed failure.

        ``frame_id`` is the Hub scene id, so a raise-first caller renders into
        the same id it raised: the ``browse`` tool keeps the default and the
        Tutorial callback passes ``z-spec-tutorial`` (ADR §5.2).
        """
        if not manifest.is_file():
            return CommandResult[BrowseResult].failed(
                CommandError(
                    CommandFailure.spec_not_found, f"Manifest not found: {manifest}"
                )
            )
        try:  # PY-EH-5 exception: manifest/spec read is an I/O boundary
            collection = self._parse_manifest(manifest)
            specs: list[tuple[SpecModel, Path]] = []
            for lesson in collection.lessons:
                tex = collection.base_path / lesson.spec_path
                if not tex.is_file():
                    return CommandResult[BrowseResult].failed(
                        CommandError(
                            CommandFailure.spec_not_found, f"Spec not found: {tex}"
                        )
                    )
                specs.append((self._parse_spec(tex), tex))
            scene = self._build(collection, specs)
        except (FileNotFoundError, ValueError) as exc:
            return CommandResult[BrowseResult].failed(
                CommandError(CommandFailure.manifest_invalid, str(exc))
            )
        try:  # PY-EH-5 exception: lux render is an I/O boundary
            self._display.show(
                scene, frame_id="z-spec-browser", frame_title=collection.title
            )
        except DisplayError as exc:
            return CommandResult[BrowseResult].failed(
                CommandError(CommandFailure.display_failed, str(exc))
            )
        return CommandResult.ok(
            BrowseResult(total=len(collection.lessons), title=collection.title)
        )
