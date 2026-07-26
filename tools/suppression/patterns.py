"""Detect and count lint/type suppression comments in one source file."""

from __future__ import annotations

import ast
import re
from typing import Self

_NOQA_RE = re.compile(r"#\s*noqa\b")
_TYPE_IGNORE_RE = re.compile(r"#\s*type:\s*ignore\b")
_PYLINT_DISABLE_RE = re.compile(r"#\s*pylint:\s*disable\b")
_PYRIGHT_IGNORE_RE = re.compile(r"#\s*pyright:\s*ignore\b")

_CODE_START_RE = re.compile(
    r"^(?:[a-zA-Z_]\w*\s*[=:([]|"
    r"(?:def|class|return|yield|raise|import|from|if|elif|else|for|while|"
    r"try|except|finally|with|assert|del|pass|break|continue|global|nonlocal)\b|@)",
)

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("noqa", _NOQA_RE),
    ("type_ignore", _TYPE_IGNORE_RE),
    ("pylint_disable", _PYLINT_DISABLE_RE),
    ("pyright_ignore", _PYRIGHT_IGNORE_RE),
)

PATTERN_NAMES: tuple[str, ...] = tuple(name for name, _ in PATTERNS)

CATEGORIES: tuple[str, ...] = (*PATTERN_NAMES, "per_file_ignores")


class FileSuppressions:
    """Count suppression comments on the code lines of one Python file."""

    _path: str
    _counts: dict[str, int]

    def __new__(cls, path: str, source: str) -> Self:
        self = super().__new__(cls)
        self._path = path
        self._counts = {name: 0 for name in PATTERN_NAMES}
        self._scan(source)
        return self

    @property
    def path(self) -> str:
        """Return the scanned file's path."""
        return self._path

    @property
    def total(self) -> int:
        """Return the total suppression count for this file."""
        return sum(self._counts.values())

    def count(self, category: str) -> int:
        """Return the count for one suppression category."""
        return self._counts.get(category, 0)

    def to_dict(self) -> dict[str, int]:
        """Return the non-zero category counts."""
        return {k: v for k, v in self._counts.items() if v}

    def _scan(self, source: str) -> None:
        for line in self._code_lines(source):
            for name, pattern in PATTERNS:
                if pattern.search(line):
                    self._counts[name] += 1

    def _code_lines(self, source: str) -> list[str]:
        """Return lines carrying code, excluding comments and string interiors."""
        lines = source.splitlines()
        if not lines:
            return []
        string_lines = self._string_line_numbers(source)
        return [
            line
            for i, line in enumerate(lines, start=1)
            if self._is_code_line(line, i, string_lines)
        ]

    @staticmethod
    def _string_line_numbers(source: str) -> set[int]:
        """Return 1-based line numbers that fall inside string literals."""
        result: set[int] = set()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return result
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.end_lineno is not None
            ):
                result.update(range(node.lineno, node.end_lineno + 1))
        return result

    @staticmethod
    def _is_code_line(line: str, lineno: int, string_lines: set[int]) -> bool:
        """Determine whether a source line carries actual code."""
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            return False
        if lineno not in string_lines:
            return True
        # Line overlaps a string literal — keep it only if it looks like code.
        if stripped.startswith(('"""', "'''")):
            return True
        return bool(_CODE_START_RE.match(stripped))
