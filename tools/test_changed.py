"""Run the default-tier tests affected by staged Git changes."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from importlib.util import resolve_name
from pathlib import Path

import pytest

_SHARED = frozenset({"Makefile", "install.sh", "pyproject.toml", "uv.lock"})
_TEST_INFRA = frozenset(
    {".github", ".githooks", "examples", "plugin", "scripts", "tools"}
)


def _imports(path: Path, package: str = "") -> set[str]:
    imported: set[str] = set()
    for node in ast.walk(ast.parse(path.read_bytes())):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level:
                if not package:
                    continue
                module = resolve_name("." * node.level + module, package)
            imported.add(module)
            imported.update(f"{module}.{alias.name}" for alias in node.names)
    return imported


def _importers(root: Path, modules: set[str]) -> set[Path] | None:
    source = root / "src"
    for path in source.rglob("*.py"):
        package = ".".join(path.relative_to(source).parts[:-1])
        if package and _imports(path, package) & modules:
            return None
    packages = {module.rpartition(".")[0] for module in modules}
    matched: set[str] = set()
    tests: set[Path] = set()
    for path in (root / "tests").rglob("test_*.py"):
        imports = _imports(path)
        matched.update(imports & modules)
        if imports & (modules | packages):
            tests.add(path.relative_to(root))
    return tests if matched == modules else None


def select_tests(root: Path, staged: set[Path]) -> list[Path] | None:
    """Return affected paths, or None when a broader change needs the default suite."""
    if any(
        path.as_posix() in _SHARED or path.parts[0] in _TEST_INFRA for path in staged
    ):
        return None
    sources = {path for path in staged if path.is_relative_to("src")}
    tests = {path for path in staged if path.is_relative_to("tests")}
    if any(
        not path.match("test_*.py") or not (root / path).is_file() for path in tests
    ):
        return None
    if any(path.suffix != ".py" or path.name == "__init__.py" for path in sources):
        return None
    if sources:
        modules = {".".join(path.with_suffix("").parts[1:]) for path in sources}
        importers = _importers(root, modules)
        if importers is None:
            return None
        tests.update(importers)
    return sorted(tests)


def main() -> int:
    """Run pytest with its default marker filter and fail on unexpected emptiness."""
    names = subprocess.check_output(
        ["git", "diff", "--cached", "--no-renames", "--name-only", "-z"]
    )
    selected = select_tests(
        Path.cwd(), {Path(os.fsdecode(name)) for name in names.split(b"\0") if name}
    )
    if selected == []:
        return 0
    command = [sys.executable, "-m", "pytest"]
    code = subprocess.call([*command, *(str(path) for path in selected or [])])
    if selected is not None and code == pytest.ExitCode.NO_TESTS_COLLECTED:
        return subprocess.call(command)
    return code


if __name__ == "__main__":
    sys.exit(main())
