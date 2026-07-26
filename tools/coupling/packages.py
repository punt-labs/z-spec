"""Package-level coupling metrics: fan-out, interface width, density, cohesion."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Self

from .graph import ImportGraph
from .layout import PackageLayout


@dataclass(frozen=True, slots=True)
class PackageMetrics:
    """One sub-package's coupling profile."""

    package: str
    modules: int
    pkg_efferent_coupling: int
    pkg_interface_width: int
    pkg_intra_density: float
    pkg_cohesion: float

    def as_dict(self) -> dict[str, float | int | str]:
        """Return the metrics as a JSON-serializable row."""
        return {
            "package": self.package,
            "modules": self.modules,
            "pkg_efferent_coupling": self.pkg_efferent_coupling,
            "pkg_interface_width": self.pkg_interface_width,
            "pkg_intra_density": self.pkg_intra_density,
            "pkg_cohesion": self.pkg_cohesion,
        }


class PackageScorer:
    """Score each sub-package of a tree against the shared import graph."""

    _layout: PackageLayout
    _graph: ImportGraph

    def __new__(cls, layout: PackageLayout, graph: ImportGraph) -> Self:
        self = super().__new__(cls)
        self._layout = layout
        self._graph = graph
        return self

    def score(self) -> list[PackageMetrics]:
        """Return metrics for every sub-package (dirs with ``__init__.py``)."""
        return [self._score_one(pkg_dir) for pkg_dir in self._sub_packages()]

    def _sub_packages(self) -> list[Path]:
        root = self._layout.root
        return [
            item.parent
            for item in sorted(root.rglob("__init__.py"))
            if item.parent != root
        ]

    def _score_one(self, pkg_dir: Path) -> PackageMetrics:
        pkg_name = str(pkg_dir.relative_to(self._layout.root)).replace("/", ".")
        keys = self._module_keys(pkg_name)
        return PackageMetrics(
            package=pkg_name,
            modules=len(keys),
            pkg_efferent_coupling=self._efferent(pkg_name, keys),
            pkg_interface_width=self._interface_width(pkg_dir),
            pkg_intra_density=self._intra_density(keys, pkg_name),
            pkg_cohesion=self._cohesion(keys),
        )

    def _module_keys(self, pkg_name: str) -> set[str]:
        prefix = f"{pkg_name}."
        return {k for k in self._graph.edges if k == pkg_name or k.startswith(prefix)}

    def _efferent(self, pkg_name: str, keys: set[str]) -> int:
        siblings: set[str] = set()
        for key in keys:
            for dep in self._graph.neighbors(key):
                dep_top = dep.split(".")[0]
                if dep_top != pkg_name and dep_top not in keys:
                    siblings.add(dep_top)
        return len(siblings)

    def _intra_density(self, keys: set[str], pkg_name: str) -> float:
        intra = sum(
            1
            for key in keys
            for dep in self._graph.neighbors(key)
            if dep in keys or dep == pkg_name
        )
        n = len(keys)
        max_edges = n * (n - 1) if n > 1 else 1
        return round(intra / max_edges, 3) if max_edges > 0 else 0.0

    def _cohesion(self, keys: set[str]) -> float:
        n = len(keys)
        if n == 0:
            return 0.0
        with_dep = sum(
            1
            for key in keys
            if any(dep in keys and dep != key for dep in self._graph.neighbors(key))
        )
        return round(with_dep / n, 3)

    def _interface_width(self, pkg_dir: Path) -> int:
        init = pkg_dir / "__init__.py"
        if not init.exists():
            return 0
        try:
            tree = ast.parse(init.read_text(), filename=str(init))
        except (SyntaxError, OSError, UnicodeDecodeError):
            # Package interface width is a display-only metric; an unreadable
            # __init__.py contributes 0 here. The gate is unaffected: the scorer
            # records the same file as an error and the ratchet fails on it when
            # touched.
            return 0
        explicit = self._all_width(tree)
        return explicit if explicit is not None else self._import_width(tree)

    @staticmethod
    def _all_width(tree: ast.Module) -> int | None:
        """Return ``len(__all__)`` for the package init, else ``None``."""
        for node in ast.iter_child_nodes(tree):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "__all__"
                    and isinstance(node.value, (ast.List, ast.Tuple))
                ):
                    return len(node.value.elts)
        return None

    @staticmethod
    def _import_width(tree: ast.Module) -> int:
        return sum(
            1
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, ast.ImportFrom) and node.module is not None
            for alias in node.names
            if not alias.name.startswith("_")
        )
