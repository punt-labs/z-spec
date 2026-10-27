"""z-spec's allow rules in the repo's ``.claude/settings.json``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from punt_zspec.claude_settings import ZSPEC_RULES, SettingsRefusedError, SettingsRules
from punt_zspec.commands.enablement import RepoEnablement

_COMMANDS_DIR = Path(__file__).resolve().parents[1] / "plugin" / "commands"


def _settings(root: Path) -> Path:
    return root / ".claude" / "settings.json"


def _write(root: Path, data: object) -> None:
    _settings(root).parent.mkdir(exist_ok=True)
    _settings(root).write_text(json.dumps(data))


def _allow(root: Path) -> list[str]:
    data = json.loads(_settings(root).read_text())
    return list(data["permissions"]["allow"])


def test_rules_cover_cli_mcp_and_every_shipped_command() -> None:
    shipped = {
        f"Skill(z-spec:{path.stem})"
        for path in _COMMANDS_DIR.glob("*.md")
        if not path.stem.endswith("-dev")
    }
    assert ZSPEC_RULES[:2] == ("Bash(z-spec:*)", "mcp__plugin_z-spec_zspec__*")
    assert set(ZSPEC_RULES[2:]) == shipped
    assert not any("-dev" in rule for rule in ZSPEC_RULES)


def test_register_creates_the_file_with_every_rule(tmp_path: Path) -> None:
    assert SettingsRules(tmp_path).register() == ZSPEC_RULES
    assert _allow(tmp_path) == list(ZSPEC_RULES)


def test_register_keeps_other_settings_and_is_idempotent(tmp_path: Path) -> None:
    _write(tmp_path, {"model": "x", "permissions": {"allow": ["Read"], "deny": ["Y"]}})
    rules = SettingsRules(tmp_path)

    rules.register()

    assert rules.register() == ()
    data = json.loads(_settings(tmp_path).read_text())
    assert data["model"] == "x"
    assert data["permissions"]["deny"] == ["Y"]
    assert data["permissions"]["allow"] == ["Read", *ZSPEC_RULES]


def test_prune_removes_exactly_the_owned_rules(tmp_path: Path) -> None:
    _write(tmp_path, {"permissions": {"allow": ["Read", *ZSPEC_RULES, "Bash(x)"]}})

    assert SettingsRules(tmp_path).prune() == ZSPEC_RULES
    assert _allow(tmp_path) == ["Read", "Bash(x)"]


def test_prune_without_a_settings_file_creates_nothing(tmp_path: Path) -> None:
    assert SettingsRules(tmp_path).prune() == ()
    assert not (tmp_path / ".claude").exists()


@pytest.mark.parametrize(
    "content",
    [b"{not json", b'{"permissions": {"allow": "Read"}}', b'{"a": "\xff"}'],
)
def test_an_unparseable_file_is_refused_untouched(
    tmp_path: Path, content: bytes
) -> None:
    _settings(tmp_path).parent.mkdir()
    _settings(tmp_path).write_bytes(content)

    with pytest.raises(SettingsRefusedError):
        SettingsRules(tmp_path).register()
    assert _settings(tmp_path).read_bytes() == content


def test_a_symlinked_settings_file_is_refused(tmp_path: Path) -> None:
    target = tmp_path / "elsewhere.json"
    target.write_text("{}")
    (tmp_path / ".claude").mkdir()
    _settings(tmp_path).symlink_to(target)

    with pytest.raises(SettingsRefusedError):
        SettingsRules(tmp_path).register()
    assert target.read_text() == "{}"


def test_a_symlinked_claude_dir_is_refused(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / ".claude").symlink_to(elsewhere)

    with pytest.raises(SettingsRefusedError):
        SettingsRules(tmp_path).register()
    assert list(elsewhere.iterdir()) == []


def test_the_home_directory_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    with pytest.raises(SettingsRefusedError):
        SettingsRules(tmp_path).register()
    assert not (tmp_path / ".claude").exists()


def test_enable_then_disable_round_trips_the_rules(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    _write(tmp_path, {"permissions": {"allow": ["Read"]}})
    enablement = RepoEnablement.for_repo(tmp_path)

    assert enablement.enable() == ZSPEC_RULES
    assert _allow(tmp_path) == ["Read", *ZSPEC_RULES]
    assert enablement.disable() == ZSPEC_RULES
    assert _allow(tmp_path) == ["Read"]


@pytest.mark.parametrize("permissions", [None, [], "x"])
def test_a_non_object_permissions_value_is_refused(
    tmp_path: Path, permissions: object
) -> None:
    _write(tmp_path, {"permissions": permissions})
    before = _settings(tmp_path).read_bytes()
    with pytest.raises(SettingsRefusedError):
        SettingsRules(tmp_path).register()
    assert _settings(tmp_path).read_bytes() == before


def test_a_refused_disable_leaves_the_repo_enabled(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    repo = RepoEnablement.for_repo(tmp_path)
    repo.enable()
    claude_md = (tmp_path / "CLAUDE.md").read_text()
    _settings(tmp_path).write_text("{not json")
    with pytest.raises(SettingsRefusedError):
        repo.disable()
    assert repo.is_enabled()
    assert (tmp_path / "CLAUDE.md").read_text() == claude_md
