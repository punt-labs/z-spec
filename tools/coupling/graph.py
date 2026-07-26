"""Build the internal import graph and find the modules caught in cycles."""

from __future__ import annotations

import ast
from typing import Self

from .imports import ImportResolver
from .layout import PackageLayout

_WHITE, _GRAY, _BLACK = 0, 1, 2


class ImportGraph:
    """A directed graph of internal package imports, keyed by module.

    Nodes are the layout's dotted module keys; an edge ``a -> b`` means module
    ``a`` imports module ``b`` from the same package. ``cycle_members`` returns
    every node on any directed cycle, which the scorer maps to the
    ``circular_imports`` metric.
    """

    _edges: dict[str, set[str]]

    def __new__(cls, edges: dict[str, set[str]]) -> Self:
        self = super().__new__(cls)
        self._edges = edges
        return self

    @classmethod
    def build(cls, layout: PackageLayout) -> Self:
        """Parse every module under ``layout`` into an import graph."""
        edges: dict[str, set[str]] = {}
        for py_file in sorted(layout.root_files()):
            key = layout.key_for(py_file)
            try:
                tree = ast.parse(py_file.read_text(), filename=str(py_file))
            except (SyntaxError, OSError, UnicodeDecodeError):
                # Unparseable/unreadable modules are omitted from the import
                # graph; the scorer records the same file as an error so the
                # ratchet still fails closed on it when it is touched.
                continue
            resolver = ImportResolver(key, layout.modules, layout.name)
            edges[key] = resolver.internal_imports(tree)
        return cls(edges)

    @property
    def edges(self) -> dict[str, set[str]]:
        """Return the adjacency map of module key to imported keys."""
        return self._edges

    def neighbors(self, node: str) -> set[str]:
        """Return the modules imported by ``node`` (empty if unknown)."""
        return self._edges.get(node, set())

    def cycle_members(self) -> set[str]:
        """Return every node that participates in any import cycle (DFS)."""
        color: dict[str, int] = dict.fromkeys(self._edges, _WHITE)
        in_cycle: set[str] = set()
        path: list[str] = []
        for node in self._edges:
            if color[node] == _WHITE:
                self._visit(node, color, path, in_cycle)
        return in_cycle

    def _visit(
        self,
        node: str,
        color: dict[str, int],
        path: list[str],
        in_cycle: set[str],
    ) -> None:
        color[node] = _GRAY
        path.append(node)
        for neighbor in self._edges.get(node, set()):
            if neighbor not in color:
                continue
            if color[neighbor] == _GRAY:
                in_cycle.update(path[path.index(neighbor) :])
            elif color[neighbor] == _WHITE:
                self._visit(neighbor, color, path, in_cycle)
        path.pop()
        color[node] = _BLACK
