"""The §2.3 state machine: enable, disable, and the §2.11 biconditional."""

from __future__ import annotations

from pathlib import Path

import pytest

from punt_zspec.commands.enablement import (
    IMPORT_LINE,
    DepositedGuide,
    RepoEnablement,
)
from punt_zspec.commands.result import CommandFailure
from punt_zspec.types import EnablementAction


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / "CLAUDE.md").write_text("# Project\n\nProse.\n")
    return tmp_path


def test_a_fresh_repo_is_not_enabled(tmp_path: Path) -> None:
    assert not RepoEnablement.for_repo(_repo(tmp_path)).is_enabled()


def test_enable_writes_marker_guide_and_import(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)

    enablement.enable()

    assert enablement.is_enabled()
    assert (root / ".punt-labs" / "z-spec" / "enabled").is_file()
    assert (root / ".punt-labs" / "z-spec" / "CLAUDE.md").read_text().startswith("#")
    assert (root / "CLAUDE.md").read_text().endswith(f"{IMPORT_LINE}\n")


def test_enable_is_idempotent(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)

    enablement.enable()
    enablement.enable()

    assert (root / "CLAUDE.md").read_text().count(IMPORT_LINE) == 1


def test_enable_redeposits_an_edited_guide(tmp_path: Path) -> None:
    # §2.2: the vendored zone is overwritten wholesale, so re-running enable is
    # the upgrade path and a local edit inside it is out of contract.
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)
    enablement.enable()
    guide = root / ".punt-labs" / "z-spec" / "CLAUDE.md"
    guide.write_text("stale\n")

    enablement.enable()

    assert guide.read_text() != "stale\n"


def test_enable_leaves_the_user_s_prose_untouched(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    RepoEnablement.for_repo(root).enable()

    assert (root / "CLAUDE.md").read_text().startswith("# Project\n\nProse.\n")


def test_disable_removes_the_marker_and_the_import(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)
    enablement.enable()

    enablement.disable()

    assert not enablement.is_enabled()
    assert not (root / ".punt-labs" / "z-spec" / "enabled").exists()
    assert IMPORT_LINE not in (root / "CLAUDE.md").read_text()


def test_disable_leaves_the_subtree_dormant(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)
    enablement.enable()

    enablement.disable()

    assert (root / ".punt-labs" / "z-spec" / "CLAUDE.md").is_file()


def test_disable_is_idempotent_on_a_never_enabled_repo(tmp_path: Path) -> None:
    root = _repo(tmp_path)

    RepoEnablement.for_repo(root).disable()

    assert (root / "CLAUDE.md").read_text() == "# Project\n\nProse.\n"


def test_enable_after_disable_returns_to_enabled(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)

    enablement.enable()
    enablement.disable()
    enablement.enable()

    assert enablement.is_enabled()
    assert (root / "CLAUDE.md").read_text().count(IMPORT_LINE) == 1


def test_a_symlinked_marker_is_not_the_signal(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)
    marker = enablement.marker_path
    marker.parent.mkdir(parents=True)
    (tmp_path / "elsewhere").touch()
    marker.symlink_to(tmp_path / "elsewhere")

    assert not enablement.is_enabled()


def test_enable_replaces_a_symlinked_marker(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)
    marker = enablement.marker_path
    marker.parent.mkdir(parents=True)
    (tmp_path / "elsewhere").touch()
    marker.symlink_to(tmp_path / "elsewhere")

    enablement.enable()

    assert enablement.is_enabled()
    assert not marker.is_symlink()


def test_for_directory_finds_the_root_from_a_subdirectory(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    nested = root / "src" / "deep"
    nested.mkdir(parents=True)

    assert RepoEnablement.for_directory(nested).root == root.resolve()


def test_for_directory_accepts_a_git_file_worktree(tmp_path: Path) -> None:
    root = tmp_path / "wt"
    root.mkdir()
    (root / ".git").write_text("gitdir: /elsewhere/.git/worktrees/wt\n")

    assert RepoEnablement.for_directory(root).root == root.resolve()


def test_for_directory_rejects_a_non_repo(tmp_path: Path) -> None:
    # The filesystem root is the one directory guaranteed to be outside a git
    # repo; a tmp_path is not, since TMPDIR lives inside this checkout.
    with pytest.raises(ValueError, match="not inside a git repository"):
        RepoEnablement.for_directory(Path(tmp_path.anchor))


def test_enable_reports_a_repo_that_refuses_the_write(tmp_path: Path) -> None:
    # A `.punt-labs` that is a regular file cannot hold the subtree. The verb
    # answers with a CommandResult like every other command, not a traceback.
    root = _repo(tmp_path)
    (root / ".punt-labs").write_text("not a directory\n")

    result = RepoEnablement.apply(EnablementAction.enable, root)

    assert not result.is_ok
    error = result.error
    assert error is not None
    assert error.kind is CommandFailure.enablement_failed
    assert "Failed to enable z-spec" in error.message


def test_disable_reports_a_repo_that_refuses_the_write(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".punt-labs").write_text("not a directory\n")

    result = RepoEnablement.apply(EnablementAction.disable, root)

    assert not result.is_ok
    assert "Failed to disable z-spec" in str(result.to_json())


def test_the_guide_ships_inside_the_package(tmp_path: Path) -> None:
    # §2.5: the guide is static content shipped with the tool, so it must be
    # readable from the installed package, not from a repo-relative path.
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)

    enablement.enable()

    assert enablement.guide_path.read_text(encoding="utf-8") == DepositedGuide.content()


def test_the_guide_names_both_verbs_and_the_marker() -> None:
    guide = DepositedGuide.content()

    assert "z-spec enable" in guide
    assert "z-spec disable" in guide
    assert ".punt-labs/z-spec/enabled" in guide


def test_the_paths_and_line_are_the_canonical_ones(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    enablement = RepoEnablement.for_repo(root)

    assert enablement.marker_path == root / ".punt-labs" / "z-spec" / "enabled"
    assert enablement.guide_path == root / ".punt-labs" / "z-spec" / "CLAUDE.md"
    assert enablement.import_line == "@.punt-labs/z-spec/CLAUDE.md"
    assert enablement.root == root
