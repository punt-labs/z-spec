"""The spec picker scene: a summary line above one tab per discovered Z spec.

A different scene from the tutorial browser next door — no manifest, no lessons,
no annotations, and its tabs come from a filesystem search rather than an
authored order. ``build_spec_picker`` is the module-level singleton the
``pick`` tool, the CLI verb, and the Browse menu callback all pass to
``PickerCommand`` as its ``PickerSceneBuilder``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

from punt_lux.protocol import GroupElement, TabBarElement, TextElement
from punt_lux.protocol.elements import Tab

from punt_zspec.applet import build_z_spec_scene
from punt_zspec.report import load_audit, load_fuzz, load_partition, load_report

if TYPE_CHECKING:
    from pathlib import Path

    from punt_zspec.types import SpecModel

__all__ = ["SpecPickerBuilder", "build_spec_picker"]


@final
class SpecPickerBuilder:
    """Render discovered specs and the root they came from as one lux scene."""

    __slots__ = ()

    def __new__(cls) -> Self:
        return super().__new__(cls)

    def __call__(
        self, specs: list[tuple[Path, SpecModel]], root: Path, /
    ) -> GroupElement:
        """Build the picker scene for ``specs`` found under ``root``."""
        return GroupElement(
            id="z-spec-picker",
            children=[self._summary(specs, root), self._tabs(specs)],
        )

    @staticmethod
    def _summary(specs: list[tuple[Path, SpecModel]], root: Path) -> TextElement:
        """Return the line naming how many specs were found, and where.

        The frame title is a constant on every surface, so without this line two
        projects raise windows that read identically and nothing on screen says
        which tree was searched.
        """
        noun = "spec" if len(specs) == 1 else "specs"
        return TextElement(
            id="z-spec-picker-summary", content=f"{len(specs)} {noun} · {root}"
        )

    @staticmethod
    def _tabs(specs: list[tuple[Path, SpecModel]]) -> TabBarElement:
        """Return one tab per spec, each labelled by its filename stem.

        A stem (``search-panel``) reads cleanly in a narrow tab strip where a
        full path would truncate to nothing, and it can never raise — unlike
        ``relative_to`` against a mismatched root.
        """
        tabs: list[Tab] = []
        for idx, (tex_path, spec) in enumerate(specs):
            spec_tabs = build_z_spec_scene(
                tex_path,
                spec,
                report=load_report(tex_path),
                fuzz=load_fuzz(tex_path),
                partition=load_partition(tex_path),
                audit=load_audit(tex_path),
                id_prefix=f"s{idx}-",
            )
            tabs.append(Tab(f"spec-{idx}", tex_path.stem, (spec_tabs,)))
        return TabBarElement(id="z-spec-picker-tabs", tabs=tabs)


build_spec_picker: SpecPickerBuilder = SpecPickerBuilder()
