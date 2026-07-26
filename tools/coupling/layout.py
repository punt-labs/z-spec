"""The module-key naming scheme for a scored package tree."""

from __future__ import annotations

from pathlib import Path
from typing import Self


class PackageLayout:
    """Map files under a package root to stable dotted module keys.

    Top-level modules key on their stem (``core``); a sub-package ``__init__``
    keys on the directory name (``voxd``); a nested module keys on its dotted
    path (``voxd.config``). The same scheme names both the coupling graph nodes
    and the discovered internal-module set, so imports resolve against keys.
    """

    _root: Path
    _name: str
    _modules: frozenset[str]

    def __new__(cls, directory: Path) -> Self:
        self = super().__new__(cls)
        self._root = directory
        self._name = directory.name
        self._modules = cls._discover(directory)
        return self

    @property
    def name(self) -> str:
        """Return the package (top directory) name."""
        return self._name

    @property
    def root(self) -> Path:
        """Return the package root directory."""
        return self._root

    @property
    def modules(self) -> frozenset[str]:
        """Return every internal module key at any depth."""
        return self._modules

    def root_files(self) -> list[Path]:
        """Return every non-hidden ``.py`` file under the package root."""
        return [
            py_file
            for py_file in sorted(self._root.rglob("*.py"))
            if not py_file.name.startswith(".")
        ]

    def key_for(self, py_file: Path) -> str:
        """Return the dotted module key for a file under the package root."""
        return self._parts_to_key(py_file.relative_to(self._root).with_suffix("").parts)

    @classmethod
    def _discover(cls, directory: Path) -> frozenset[str]:
        names: set[str] = set()
        for py_file in sorted(directory.rglob("*.py")):
            if py_file.name.startswith("."):
                continue
            parts = py_file.relative_to(directory).with_suffix("").parts
            names.add(cls._parts_to_key(parts))
        return frozenset(names)

    @staticmethod
    def _parts_to_key(parts: tuple[str, ...]) -> str:
        if len(parts) == 1:
            return parts[0]
        if parts[-1] == "__init__":
            return ".".join(parts[:-1])
        return ".".join(parts)
