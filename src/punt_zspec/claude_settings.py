"""z-spec's allow rules in the repo's ``.claude/settings.json``.

``z-spec enable`` is the user's consent to let Claude run z-spec without a
prompt in this repo, so it adds the CLI, MCP and command rules below; ``z-spec
disable`` removes these exact values. Nothing here touches the user-global
``~/.claude/settings.json`` (punt-kit ``permissions.md`` §6).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final, Self, cast, final

from punt_zspec.atomic_file import AtomicFile

__all__ = ["ZSPEC_RULES", "SettingsRefusedError", "SettingsRules"]

_COMMANDS: Final = (
    "audit",
    "b-animate",
    "b-check",
    "b-create",
    "b-refine",
    "check",
    "cleanup",
    "code2model",
    "contracts",
    "disable",
    "doctor",
    "elaborate",
    "enable",
    "help",
    "model2code",
    "oracle",
    "partition",
    "prove",
    "refine",
    "setup",
    "test",
)

# The deterministic rule set: enable adds every missing member, disable removes
# these exact values. A rule retired here strands on disable, so it stays in the
# set until no enabled repo can still carry it. No ``z-spec-dev`` rule: the dev
# plugin only exists in a maintainer's checkout.
ZSPEC_RULES: Final = (
    "Bash(z-spec:*)",
    "mcp__plugin_z-spec_zspec__*",
    *(f"Skill(z-spec:{name})" for name in _COMMANDS),
)


class SettingsRefusedError(OSError):
    """The settings file was left untouched because editing it is unsafe."""


@final
class SettingsRules:
    """Owns a fixed set of ``permissions.allow`` entries in one settings file."""

    _root: Path
    _rules: tuple[str, ...]
    __slots__ = ("_root", "_rules")

    def __new__(cls, root: Path, rules: tuple[str, ...] = ZSPEC_RULES) -> Self:
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
        return self._update(grant=True)

    def prune(self) -> tuple[str, ...]:
        """Remove every owned rule; return those removed."""
        if not self.path.is_file() and not self.path.is_symlink():
            return ()
        return self._update(grant=False)

    def _update(self, *, grant: bool) -> tuple[str, ...]:
        self._refuse_unsafe()
        host = AtomicFile(self.path)
        with host.locked():
            data = self._parse(host.read())
            allow = data.setdefault("permissions", {}).setdefault("allow", [])
            if grant:
                changed = tuple(rule for rule in self._rules if rule not in allow)
                allow.extend(changed)
            else:
                changed = tuple(rule for rule in self._rules if rule in allow)
                allow[:] = [rule for rule in allow if rule not in self._rules]
            if changed:
                host.write(json.dumps(data, indent=2) + "\n")
            return changed

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
        permissions: object = parsed.get("permissions", {})
        if not isinstance(permissions, dict):
            msg = f"{self.path} has no editable permissions object"
            raise SettingsRefusedError(msg)
        allow: object = cast("dict[str, Any]", permissions).get("allow", [])
        if not isinstance(allow, list):
            msg = f"{self.path} has no editable permissions.allow list"
            raise SettingsRefusedError(msg)
        return parsed
