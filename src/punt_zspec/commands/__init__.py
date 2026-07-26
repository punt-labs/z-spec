"""Orchestration commands shared by the CLI and MCP surfaces."""

from __future__ import annotations

from punt_zspec.commands.animate import AnimateCommand
from punt_zspec.commands.audit import AuditCommand
from punt_zspec.commands.browse import BrowseCommand
from punt_zspec.commands.check import CheckCommand
from punt_zspec.commands.doctor import DoctorCommand
from punt_zspec.commands.model_check import ModelCheckCommand
from punt_zspec.commands.partition import PartitionCommand
from punt_zspec.commands.registry import CAPABILITIES, Capability
from punt_zspec.commands.report import ReportCommand
from punt_zspec.commands.result import (
    CommandError,
    CommandFailure,
    CommandResult,
)
from punt_zspec.commands.show import ShowCommand
from punt_zspec.commands.test import TestCommand

__all__ = [
    "CAPABILITIES",
    "AnimateCommand",
    "AuditCommand",
    "BrowseCommand",
    "Capability",
    "CheckCommand",
    "CommandError",
    "CommandFailure",
    "CommandResult",
    "DoctorCommand",
    "ModelCheckCommand",
    "PartitionCommand",
    "ReportCommand",
    "ShowCommand",
    "TestCommand",
]
