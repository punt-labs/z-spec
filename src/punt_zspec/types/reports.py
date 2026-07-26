"""The persisted-report bundle: a snapshot of the four reports beside a spec."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final

from .audit import AuditReport
from .fuzz import FuzzResult
from .partition import PartitionReport
from .prob import ProbReport


@final
@dataclass(frozen=True, slots=True)
class SpecReports:
    """A frozen snapshot of the four reports persisted beside a spec.

    Each field is optional because a spec may have no report of that kind yet —
    absence is the documented contract, not a failure (PY-TS-14).
    """

    report: ProbReport | None
    fuzz: FuzzResult | None
    partition: PartitionReport | None
    audit: AuditReport | None
