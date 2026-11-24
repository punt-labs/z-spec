"""Exercise local test selection and enforcement of quarantine metadata."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from tools.test_changed import select_tests
from tools.test_quarantine import pytest_collection_modifyitems, quarantine_is_valid

_ROOT = Path(__file__).resolve().parents[1]


def test_precommit_tests_the_index_not_the_working_tree(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Tester",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "baseline",
        ],
        cwd=tmp_path,
        check=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    (tmp_path / "tests").mkdir()
    probe = tmp_path / "tests/test_probe.py"
    probe.write_text(
        "import subprocess\n"
        "def test_probe():\n"
        "    current = subprocess.check_output("
        "['git', 'rev-parse', 'HEAD'], text=True)\n"
        f"    assert current.strip() == {head!r}\n"
        "    assert False, 'index-only failure'\n"
    )
    subprocess.run(["git", "add", "tests/test_probe.py"], cwd=tmp_path, check=True)
    probe.write_text("def test_probe():\n    assert True\n")

    result = subprocess.run(
        [sys.executable, str(_ROOT / "tools/test_changed.py")],
        cwd=tmp_path,
        env={**os.environ, "PYTEST_ADDOPTS": f"--basetemp={tmp_path / 'child'}"},
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 1, result.stderr
    assert "AssertionError: index-only failure" in result.stdout
    assert probe.read_text() == "def test_probe():\n    assert True\n"


@pytest.fixture
def prepush_hook(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Tester",
            "-c",
            "user.email=test@example.com",
            "commit",
            "--quiet",
            "--allow-empty",
            "-m",
            "probe",
        ],
        cwd=tmp_path,
        check=True,
    )
    hooks = tmp_path / ".githooks"
    hooks.mkdir()
    installed = hooks / "pre-push"
    installed.write_bytes((_ROOT / ".githooks/pre-push").read_bytes())
    installed.chmod(0o755)
    (tmp_path / "Makefile").write_text("test-push:\n\t@echo ran-push-gate\n")
    return installed


def test_prepush_refuses_to_test_a_different_commit(
    tmp_path: Path, prepush_hook: Path
) -> None:
    result = subprocess.run(
        [str(prepush_hook)],
        cwd=tmp_path,
        input=f"refs/heads/other {'1' * 40} refs/heads/other {'0' * 40}\n",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    assert "check it out and push it separately" in result.stderr


def test_prepush_accepts_tag_at_head(tmp_path: Path, prepush_hook: Path) -> None:
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Tester",
            "-c",
            "user.email=test@example.com",
            "tag",
            "-a",
            "v1",
            "-m",
            "probe",
        ],
        cwd=tmp_path,
        check=True,
    )
    tag = subprocess.check_output(
        ["git", "rev-parse", "refs/tags/v1"], cwd=tmp_path, text=True
    ).strip()
    result = subprocess.run(
        [str(prepush_hook)],
        cwd=tmp_path,
        input=f"refs/tags/v1 {tag} refs/tags/v1 {'0' * len(tag)}\n",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ran-push-gate" in result.stdout


def test_prepush_replays_refs_and_args_to_chained_hook(
    tmp_path: Path, prepush_hook: Path
) -> None:
    custom_hook = tmp_path / "custom-hook"
    custom_hook.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > args\ncat > refs\n')
    custom_hook.chmod(0o755)
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    refs = f"HEAD {head} refs/heads/main {'0' * len(head)}\n"
    result = subprocess.run(
        [str(prepush_hook), "--chain", str(custom_hook), "origin", "remote-url"],
        cwd=tmp_path,
        input=refs,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ran-push-gate" in result.stdout
    assert (tmp_path / "args").read_text() == "origin\nremote-url\n"
    assert (tmp_path / "refs").read_text() == refs


def test_prepush_runs_gate_after_an_upstream_hook_consumes_refs(
    tmp_path: Path, prepush_hook: Path
) -> None:
    result = subprocess.run(
        ["sh", "-c", 'cat >/dev/null; exec "$@"', "pre-push", str(prepush_hook)],
        cwd=tmp_path,
        input="a ref update consumed by the preceding hook\n",
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "ran-push-gate" in result.stdout


def test_changed_module_and_test_select_relevant_paths(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    matching = tests / "test_fuzz.py"
    matching.write_text("from punt_zspec.fuzz import resolve_fuzz\n")
    unrelated = tests / "test_prob.py"
    unrelated.write_text("from punt_zspec.prob import resolve_probcli\n")
    staged = {Path("src/punt_zspec/fuzz.py"), unrelated.relative_to(tmp_path)}

    assert select_tests(tmp_path, staged) == sorted(
        path.relative_to(tmp_path) for path in (matching, unrelated)
    )


@pytest.mark.parametrize(
    "path", ["tests/conftest.py", "src/punt_zspec/unmapped.py", "uv.lock"]
)
def test_shared_or_unmapped_changes_select_default_suite(
    tmp_path: Path, path: str
) -> None:
    assert select_tests(tmp_path, {Path(path)}) is None


def test_docs_only_changes_do_not_select_python_tests(tmp_path: Path) -> None:
    assert select_tests(tmp_path, {Path("TESTING.md")}) == []


def test_oracle_protocol_doc_selects_its_prompt_contract() -> None:
    assert select_tests(_ROOT, {Path("docs/prd/z-oracle.md")}) == [
        Path("tests/commands/test_prompt_contracts.py")
    ]


def test_indirect_source_consumers_select_default_suite(tmp_path: Path) -> None:
    source = tmp_path / "src/punt_zspec"
    source.mkdir(parents=True)
    (source / "command.py").write_text("from .prob import run_model_check\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_prob.py").write_text("from punt_zspec.prob import run_model_check\n")

    assert select_tests(tmp_path, {Path("src/punt_zspec/prob.py")}) is None


@pytest.mark.parametrize(
    ("issue", "owner", "reason", "expires", "valid"),
    [
        ("PL-12", "tester", "intermittent timeout", "2026-11-24", True),
        ("PL-12", "tester", "intermittent timeout", "2026-12-08", True),
        ("#12", "tester", "intermittent timeout", "2026-11-25", False),
        ("PL-12", " ", "intermittent timeout", "2026-11-25", False),
        ("PL-12", "tester", "", "2026-11-25", False),
        ("PL-12", "tester", "intermittent timeout", "2026-11-23", False),
        ("PL-12", "tester", "intermittent timeout", "2026-12-09", False),
        ("PL-12", "tester", "intermittent timeout", "2026-11-31", False),
    ],
)
def test_quarantine_requires_an_owned_and_near_term_deadline(
    issue: str, owner: str, reason: str, expires: str, valid: bool
) -> None:
    mark = pytest.mark.quarantine(
        issue=issue, owner=owner, reason=reason, expires=expires
    ).mark
    assert quarantine_is_valid(mark, date(2026, 11, 24)) is valid


def test_collection_rejects_invalid_quarantine() -> None:
    item = Mock(spec=pytest.Item, nodeid="tests/test_example.py::test_flaky")
    item.iter_markers.return_value = [pytest.mark.quarantine().mark]

    with pytest.raises(pytest.UsageError, match="test_flaky: quarantine requires"):
        pytest_collection_modifyitems([item])


@pytest.mark.parametrize("expired", [True, False])
def test_quarantine_is_enforced_during_real_collection(
    tmp_path: Path, expired: bool
) -> None:
    (tmp_path / "conftest.py").write_bytes((_ROOT / "tests/conftest.py").read_bytes())
    expires = "2000-01-01" if expired else datetime.now(UTC).date().isoformat()
    (tmp_path / "test_probe.py").write_text(
        "import pytest\n"
        f"@pytest.mark.quarantine(issue='PL-1', owner='tester', "
        f"reason='probe', expires={expires!r})\n"
        "def test_quarantined():\n    pass\n"
        "def test_default():\n    pass\n"
    )
    args = ["--collect-only"] if expired else ["-m", "quarantine"]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            str(_ROOT / "pyproject.toml"),
            "--rootdir",
            str(tmp_path),
            *args,
            "test_probe.py",
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": str(_ROOT),
            "PYTEST_ADDOPTS": f"--basetemp={tmp_path / 'child'}",
        },
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if expired:
        assert result.returncode == pytest.ExitCode.USAGE_ERROR
        assert "test_quarantined: quarantine requires" in result.stderr
    else:
        assert result.returncode == 0, result.stderr
        assert "1 passed, 1 deselected" in result.stdout
