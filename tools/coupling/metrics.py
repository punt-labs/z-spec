"""Coupling and cohesion metrics for a single parsed Python module."""

from __future__ import annotations

import ast
from itertools import combinations
from typing import Self

from .imports import ImportResolver

_TYPE_BASES = frozenset({"Protocol", "TypedDict"})


class ModuleCouplingMetrics:
    """Compute one module's efferent coupling, interface width, and LCOM.

    ``circular_imports`` is left at 0 here and filled in by the scorer once the
    whole-package import graph is known -- a single module cannot see a cycle it
    only participates in.
    """

    _path: str
    _tree: ast.Module
    _resolver: ImportResolver

    def __new__(cls, path: str, tree: ast.Module, resolver: ImportResolver) -> Self:
        self = super().__new__(cls)
        self._path = path
        self._tree = tree
        self._resolver = resolver
        return self

    def compute(self) -> dict[str, float | int | str]:
        """Return every per-module metric as a JSON-serializable dict."""
        lcom_values = self._lcom_values()
        return {
            "file": self._path,
            "efferent_coupling": len(self._resolver.internal_imports(self._tree)),
            "public_names": self._public_names(),
            "circular_imports": 0,  # filled by the scorer after graph analysis
            "max_lcom": max(lcom_values) if lcom_values else 0.0,
            "avg_lcom": (
                round(sum(lcom_values) / len(lcom_values), 3) if lcom_values else 0.0
            ),
        }

    # ---- public interface width ----

    def _public_names(self) -> int:
        explicit = self._all_count()
        return explicit if explicit is not None else self._heuristic_count()

    def _all_count(self) -> int | None:
        """Return ``len(__all__)`` if the module declares it, else ``None``."""
        for node in ast.iter_child_nodes(self._tree):
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

    def _heuristic_count(self) -> int:
        return sum(
            self._node_public_names(node) for node in ast.iter_child_nodes(self._tree)
        )

    @staticmethod
    def _node_public_names(node: ast.AST) -> int:
        if isinstance(node, ast.ClassDef):
            return 0 if node.name.startswith("_") else 1
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return 0 if node.name.startswith("_") else 1
        if isinstance(node, ast.Assign):
            return sum(
                1
                for t in node.targets
                if isinstance(t, ast.Name) and not t.id.startswith("_")
            )
        return 0

    # ---- LCOM cohesion ----

    def _lcom_values(self) -> list[float]:
        values: list[float] = []
        for node in ast.iter_child_nodes(self._tree):
            if not isinstance(node, ast.ClassDef) or self._is_type_definition(node):
                continue
            lcom = self._class_lcom(node)
            if lcom is not None:
                values.append(lcom)
        return values

    def _class_lcom(self, cls_node: ast.ClassDef) -> float | None:
        """Return the class's LCOM, or ``None`` when it has < 2 instance methods."""
        methods = self._instance_method_attrs(cls_node)
        if len(methods) <= 1:
            return None
        return self._lcom_from(methods)

    def _instance_method_attrs(self, cls_node: ast.ClassDef) -> list[set[str]]:
        methods: list[set[str]] = []
        for item in ast.iter_child_nodes(cls_node):
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if self._is_static_or_class(item):
                continue
            methods.append(self._method_self_attrs(item))
        return methods

    @staticmethod
    def _is_static_or_class(item: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        marks = {"staticmethod", "classmethod"}
        for dec in item.decorator_list:
            if isinstance(dec, ast.Name) and dec.id in marks:
                return True
            if isinstance(dec, ast.Attribute) and dec.attr in marks:
                return True
        return False

    @staticmethod
    def _method_self_attrs(method: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        return {
            node.attr
            for node in ast.walk(method)
            if isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
            and node.attr.startswith("_")
        }

    @staticmethod
    def _lcom_from(methods: list[set[str]]) -> float:
        total = 0
        disjoint = 0
        for m1, m2 in combinations(methods, 2):
            total += 1
            if not m1 & m2:
                disjoint += 1
        return round(disjoint / total, 3) if total else 0.0

    @staticmethod
    def _is_type_definition(node: ast.ClassDef) -> bool:
        """Return True for Protocol/TypedDict classes (excluded from LCOM)."""
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in _TYPE_BASES:
                return True
            if (
                isinstance(base, ast.Subscript)
                and isinstance(base.value, ast.Name)
                and base.value.id in _TYPE_BASES
            ):
                return True
        return False
