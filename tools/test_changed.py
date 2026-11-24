"""Run the default-tier tests affected by staged Git changes."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from importlib.util import resolve_name
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

_SHARED = frozenset({"Makefile", "install.sh", "pyproject.toml", "uv.lock"})
_DOC_TESTS = {
    Path("docs/prd/z-oracle.md"): Path("tests/commands/test_prompt_contracts.py"),
}
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
    tests.update(_DOC_TESTS[path] for path in staged if path in _DOC_TESTS)
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
    staged = {Path(os.fsdecode(name)) for name in names.split(b"\0") if name}
    if not staged:
        return 0
    git_env = subprocess.check_output(
        ["git", "rev-parse", "--local-env-vars"], text=True
    )
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in git_env.splitlines()
    }
    with TemporaryDirectory(prefix="z-spec-staged-") as temp:
        root = Path(temp)
        subprocess.run(
            ["git", "clone", "--quiet", "--shared", "--no-checkout", ".", temp],
            env=env,
            check=True,
        )
        subprocess.run(
            [
                "git",
                "checkout-index",
                "--all",
                "--ignore-skip-worktree-bits",
                f"--prefix={root}/",
            ],
            check=True,
        )
        env["PYTHONPATH"] = os.pathsep.join((str(root / "src"), str(root)))
        selected = select_tests(root, staged)
        if selected == []:
            return 0
        command = [sys.executable, "-m", "pytest"]
        code = subprocess.call(
            [*command, *(str(path) for path in selected or [])], cwd=root, env=env
        )
        if selected is not None and code == pytest.ExitCode.NO_TESTS_COLLECTED:
            return subprocess.call(command, cwd=root, env=env)
        return code


if __name__ == "__main__":
    sys.exit(main())
