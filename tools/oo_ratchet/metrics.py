"""AST-derived object-orientation metrics for a single Python module."""

from __future__ import annotations

import ast
from collections.abc import Iterator
from typing import Self


class ModuleMetrics:
    """Compute OO quality metrics for one parsed module."""

    _path: str
    _tree: ast.Module
    _source_lines: int

    def __new__(cls, path: str, source: str) -> Self:
        self = super().__new__(cls)
        self._path = path
        self._tree = ast.parse(source, filename=path)
        self._source_lines = len([line for line in source.splitlines() if line.strip()])
        return self

    def compute(self) -> dict[str, float | int | str]:
        """Return the full metric dict for this module."""
        return {
            "file": self._path,
            "module_size": self._source_lines,
            "classes_per_module": self._count_classes(),
            "top_level_functions": self._count_top_level_functions(),
            "top_level_statements": self._count_top_level_statements(),
            "method_ratio": self._method_ratio(),
            "class_to_func_ratio": self._class_to_func_ratio(),
            "encapsulation_ratio": self._encapsulation_ratio(),
            "avg_params": self._avg_params(),
            "max_complexity": self._max_complexity(),
            "avg_complexity": self._avg_complexity(),
            "init_violations": self._count_init(),
            "public_attr_violations": self._count_public_attrs(),
            "future_annotations": self._has_future_annotations(),
        }

    def _count_classes(self) -> int:
        return sum(
            1
            for node in ast.iter_child_nodes(self._tree)
            if isinstance(node, ast.ClassDef) and not self._is_type_definition(node)
        )

    @staticmethod
    def _is_type_definition(node: ast.ClassDef) -> bool:
        type_bases = {"Protocol", "TypedDict"}
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id in type_bases:
                return True
            if (
                isinstance(base, ast.Subscript)
                and isinstance(base.value, ast.Name)
                and base.value.id in type_bases
            ):
                return True
        return False

    def _count_top_level_functions(self) -> int:
        return sum(
            1
            for node in ast.iter_child_nodes(self._tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        )

    def _count_top_level_statements(self) -> int:
        skip_types = (
            ast.Import,
            ast.ImportFrom,
            ast.ClassDef,
            ast.FunctionDef,
            ast.AsyncFunctionDef,
        )
        count = 0
        for node in ast.iter_child_nodes(self._tree):
            if isinstance(node, skip_types):
                continue
            if (
                isinstance(node, ast.Expr)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                continue
            count += 1
        return count

    def _count_methods(self) -> int:
        count = 0
        for node in ast.walk(self._tree):
            if isinstance(node, ast.ClassDef):
                for item in ast.iter_child_nodes(node):
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        count += 1
        return count

    def _method_ratio(self) -> float:
        methods = self._count_methods()
        top_funcs = self._count_top_level_functions()
        total = methods + top_funcs
        if total == 0:
            top_stmts = self._count_top_level_statements()
            return 0.0 if top_stmts > 5 else 1.0
        return round(methods / total, 3)

    def _class_to_func_ratio(self) -> float:
        classes = self._count_classes()
        funcs = self._count_top_level_functions()
        total = classes + funcs
        if total == 0:
            top_stmts = self._count_top_level_statements()
            return 0.0 if top_stmts > 5 else 1.0
        return round(classes / total, 3)

    def _self_attr_names(self) -> Iterator[str]:
        """Yield the attribute name of every ``self.<attr> = ...`` assignment."""
        for node in ast.walk(self._tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign) and node.target is not None:
                targets = [node.target]
            for target in targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    yield target.attr

    def _encapsulation_ratio(self) -> float:
        attrs = list(self._self_attr_names())
        if not attrs:
            return 1.0
        private = sum(1 for attr in attrs if attr.startswith("_"))
        return round(private / len(attrs), 3)

    def _avg_params(self) -> float:
        counts = []
        for node in ast.walk(self._tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            param_count = len(args.args) + len(args.posonlyargs) + len(args.kwonlyargs)
            # The receiver is the first positional parameter, which lives in
            # posonlyargs for a PEP-570 signature (`def m(self, x, /)`) and in
            # args otherwise. Subtract it in both cases.
            leading = args.posonlyargs or args.args
            if leading and leading[0].arg in ("self", "cls"):
                param_count -= 1
            counts.append(param_count)
        if not counts:
            return 0.0
        return round(sum(counts) / len(counts), 2)

    def _max_complexity(self) -> int:
        max_cc = 0
        for node in ast.walk(self._tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cc = self._cyclomatic_complexity(node)
                max_cc = max(max_cc, cc)
        return max_cc

    def _avg_complexity(self) -> float:
        complexities = [
            self._cyclomatic_complexity(node)
            for node in ast.walk(self._tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if not complexities:
            return 0.0
        return round(sum(complexities) / len(complexities), 2)

    @staticmethod
    def _cyclomatic_complexity(
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> int:
        cc = 1
        for node in ast.walk(func_node):
            if isinstance(
                node,
                (ast.If, ast.While, ast.For, ast.AsyncFor, ast.ExceptHandler),
            ):
                cc += 1
            elif isinstance(node, ast.BoolOp):
                cc += len(node.values) - 1
            elif isinstance(node, ast.Assert):
                cc += 1
            elif isinstance(node, ast.comprehension):
                cc += 1 + len(node.ifs)
        return cc

    @staticmethod
    def _has_dataclass_decorator(node: ast.ClassDef) -> bool:
        for d in node.decorator_list:
            if isinstance(d, ast.Name) and d.id == "dataclass":
                return True
            if (
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Name)
                and d.func.id == "dataclass"
            ):
                return True
            if isinstance(d, ast.Attribute) and d.attr == "dataclass":
                return True
        return False

    def _count_init(self) -> int:
        count = 0
        for node in ast.walk(self._tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if self._has_dataclass_decorator(node):
                continue
            for item in ast.iter_child_nodes(node):
                if isinstance(item, ast.FunctionDef) and item.name == "__init__":
                    count += 1
        return count

    def _count_public_attrs(self) -> int:
        return sum(1 for attr in self._self_attr_names() if not attr.startswith("_"))

    def _has_future_annotations(self) -> int:
        for node in ast.iter_child_nodes(self._tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "__future__"
                and any(alias.name == "annotations" for alias in node.names)
            ):
                return 1
        return 0
