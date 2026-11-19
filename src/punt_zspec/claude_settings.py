"""z-spec's permission rules in the repo's ``.claude/settings.json``.

``z-spec enable`` is the user's consent to let Claude run z-spec without a
prompt in this repo, so it adds the allow and ask rules below; ``z-spec
disable`` removes these exact values. Nothing here touches the user-global
``~/.claude/settings.json`` (punt-kit ``permissions.md`` §6).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Self, cast, final

from punt_zspec.atomic_file import AtomicFile

__all__ = ["ZSPEC_RULES", "SettingsRefusedError", "SettingsRules"]

# Broad allow per surface, exact ask carve-outs (permissions.md § 6): ask beats
# allow, so the carve-outs prompt while new safe commands work unprompted. The
# carve-outs change enablement or permissions (enable, disable, the enablement
# MCP tool and its skills) or install software (``z-spec mcp``, /z-spec:setup,
# whose allowed-tools run brew, curl, make). A global option before the verb
# runs under the broad allow: the ask tier is a safety net, not a boundary
# (punt-kit DES-039). No ``z-spec-dev`` rule: the dev plugin only exists in a
# maintainer's checkout.
# Disable removes these exact values from both lists.
ZSPEC_RULES: Final[dict[str, tuple[str, ...]]] = {
    "allow": ("Bash(z-spec:*)", "mcp__plugin_z-spec_zspec__*", "Skill(z-spec:*)"),
    "ask": (
        *(f"Bash(z-spec {verb}:*)" for verb in ("enable", "disable", "mcp")),
        "mcp__plugin_z-spec_zspec__enablement",
        *(f"Skill(z-spec:{cmd})" for cmd in ("enable", "disable", "setup")),
    ),
}
# Retired rules that register and prune both strip from the settings file.
# ``Bash(z-spec -*)`` would make ``z-spec --version`` prompt.
_LEGACY_RULES: Final[dict[str, tuple[str, ...]]] = {"ask": ("Bash(z-spec -*)",)}


class SettingsRefusedError(OSError):
    """The settings file was left untouched because editing it is unsafe."""


@final
class SettingsRules:
    """Owns fixed ``permissions.allow`` and ``permissions.ask`` entries in one file."""

    _root: Path
    _rules: dict[str, tuple[str, ...]]
    __slots__ = ("_root", "_rules")

    def __new__(
        cls, root: Path, rules: dict[str, tuple[str, ...]] = ZSPEC_RULES
    ) -> Self:
        """Bind ``rules`` to the settings file under ``root``.

        Args:
            root: The repository whose ``.claude/settings.json`` is edited.
            rules: Rule strings keyed by permission tier (``allow`` or ``ask``).
        """
        self = super().__new__(cls)
        self._root = root
        self._rules = rules
        return self

    @property
    def path(self) -> Path:
        """Return the settings file path."""
        return self._root / ".claude" / "settings.json"

    def register(self) -> tuple[str, ...]:
        """Append each missing rule, creating the file if absent; return those added."""
        return self._update(grant=True)[0]

    def prune(self) -> tuple[str, ...]:
        """Remove every owned rule; return those removed."""
        if not self.path.is_file() and not self.path.is_symlink():
            return ()
        changed, retired = self._update(grant=False)
        return (*changed, *retired)

    def _update(self, *, grant: bool) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Apply the edit; return the owned rules changed and legacy rules removed."""
        self._refuse_unsafe()
        host = AtomicFile(self.path)
        with host.locked():
            data = self._parse(host.read())
            permissions = data.setdefault("permissions", {})
            changed = tuple(
                rule
                for tier, owned in self._rules.items()
                for rule in self._edit(
                    permissions.setdefault(tier, [])
                    if grant
                    else permissions.get(tier, []),
                    owned,
                    grant=grant,
                )
            )
            retired = self._strip_legacy(permissions)
            if changed or retired:
                host.write(json.dumps(data, indent=2) + "\n")
            return changed, retired

    @staticmethod
    def _strip_legacy(permissions: dict[str, Any]) -> tuple[str, ...]:
        """Remove every legacy rule from *permissions*; return those removed."""
        removed: tuple[str, ...] = ()
        for tier, legacy in _LEGACY_RULES.items():
            have = permissions.get(tier, [])
            removed = (*removed, *(rule for rule in have if rule in legacy))
            have[:] = [rule for rule in have if rule not in legacy]
        return removed

    @staticmethod
    def _edit(
        have: list[str], owned: tuple[str, ...], *, grant: bool
    ) -> tuple[str, ...]:
        """Add the missing *owned* rules to *have*, or remove them; return those."""
        if grant:
            added = tuple(rule for rule in owned if rule not in have)
            have.extend(added)
            return added
        removed = tuple(rule for rule in owned if rule in have)
        have[:] = [rule for rule in have if rule not in owned]
        return removed

    def _refuse_unsafe(self) -> None:
        if self._root.resolve() == Path.home().resolve():
            msg = "the repository is your home directory"
            raise SettingsRefusedError(msg)
        for path in (self.path.parent, self.path):
            if path.is_symlink():
                msg = f"{path} is a symlink"
                raise SettingsRefusedError(msg)

    def _parse(self, text: str) -> dict[str, Any]:
        if not text.strip():
            return {}
        try:
            text.encode("utf-8")
            data: object = json.loads(text)
        except (UnicodeEncodeError, json.JSONDecodeError) as exc:
            msg = f"{self.path} is not valid UTF-8 JSON"
            raise SettingsRefusedError(msg) from exc
        if not isinstance(data, dict):
            msg = f"{self.path} is not a JSON object"
            raise SettingsRefusedError(msg)
        parsed = cast("dict[str, Any]", data)
        self._check_permissions(parsed.get("permissions", {}))
        return parsed

    def _check_permissions(self, permissions: object) -> None:
        """Refuse a ``permissions`` value or owned tier that is not editable."""
        if not isinstance(permissions, dict):
            msg = f"{self.path} has no editable permissions object"
            raise SettingsRefusedError(msg)
        for tier in self._rules:
            rules: object = cast("dict[str, Any]", permissions).get(tier, [])
            if not isinstance(rules, list):
                msg = f"{self.path} has no editable permissions.{tier} list"
                raise SettingsRefusedError(msg)
