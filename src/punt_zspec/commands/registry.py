"""The canonical list of capabilities and their name on each surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from punt_zspec.commands.animate import AnimateCommand
from punt_zspec.commands.audit import AuditCommand
from punt_zspec.commands.browse import BrowseCommand
from punt_zspec.commands.check import CheckCommand
from punt_zspec.commands.disable import DisableCommand
from punt_zspec.commands.doctor import DoctorCommand
from punt_zspec.commands.enable import EnableCommand
from punt_zspec.commands.model_check import ModelCheckCommand
from punt_zspec.commands.partition import PartitionCommand
from punt_zspec.commands.picker import PickerCommand
from punt_zspec.commands.report import ReportCommand
from punt_zspec.commands.show import ShowCommand
from punt_zspec.commands.test import TestCommand


@final
@dataclass(frozen=True, slots=True)
class Capability:
    """One deterministic capability and its verb/tool spelling per surface.

    The CLI verb and MCP tool names differ by design (``model-check`` vs
    ``model_check``, ``report`` vs ``get_report``), so both are recorded here
    and the parity test enforces each surface matches this registry.

    Two capabilities may name the same MCP tool: ``enable`` and ``disable`` are
    two CLI verbs but one ``enablement`` tool taking an action argument, the
    form punt-kit ``tool-enable-disable.md`` §2.14 requires.
    """

    name: str  # canonical id, e.g. "partition"
    command: type  # the @final command class
    cli_verb: str  # Typer command name, e.g. "partition"
    mcp_tool: str  # FastMCP tool name, e.g. "save_partition_report"


CAPABILITIES: tuple[Capability, ...] = (
    Capability("check", CheckCommand, "check", "check"),
    Capability("test", TestCommand, "test", "test"),
    Capability("animate", AnimateCommand, "animate", "animate"),
    Capability("model-check", ModelCheckCommand, "model-check", "model_check"),
    Capability("report", ReportCommand, "report", "get_report"),
    Capability("doctor", DoctorCommand, "doctor", "doctor"),
    Capability("partition", PartitionCommand, "partition", "save_partition_report"),
    Capability("audit", AuditCommand, "audit", "save_audit_report"),
    Capability("show", ShowCommand, "show", "show_z_spec"),
    Capability("browse", BrowseCommand, "browse", "browse"),
    Capability("pick", PickerCommand, "pick", "pick"),
    Capability("enable", EnableCommand, "enable", "enablement"),
    Capability("disable", DisableCommand, "disable", "enablement"),
)
