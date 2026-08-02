"""The enablement report's wire form and the two-verb vocabulary."""

from __future__ import annotations

from pathlib import Path

from punt_zspec.types import EnablementAction, EnablementReport


def _report(action: EnablementAction, *, enabled: bool) -> EnablementReport:
    root = Path("/repo")
    return EnablementReport(
        action=action,
        root=root,
        marker=root / ".punt-labs" / "z-spec" / "enabled",
        guide=root / ".punt-labs" / "z-spec" / "CLAUDE.md",
        import_line="@.punt-labs/z-spec/CLAUDE.md",
        enabled=enabled,
    )


def test_the_vocabulary_is_exactly_two_verbs() -> None:
    # §2.3: enable / disable, no boolean toggle and no third state.
    assert [a.value for a in EnablementAction] == ["enable", "disable"]


def test_an_action_serializes_as_its_verb() -> None:
    assert str(EnablementAction.enable) == "enable"
    assert str(EnablementAction.disable) == "disable"


def test_to_dict_carries_the_verb_and_the_resulting_state() -> None:
    wire = _report(EnablementAction.enable, enabled=True).to_dict()

    assert wire == {
        "ok": True,
        "action": "enable",
        "enabled": True,
        "root": str(Path("/repo")),
        "marker": str(Path("/repo/.punt-labs/z-spec/enabled")),
        "guide": str(Path("/repo/.punt-labs/z-spec/CLAUDE.md")),
        "import_line": "@.punt-labs/z-spec/CLAUDE.md",
    }


def test_disable_reports_the_off_state() -> None:
    wire = _report(EnablementAction.disable, enabled=False).to_dict()

    assert wire["action"] == "disable"
    assert wire["enabled"] is False
