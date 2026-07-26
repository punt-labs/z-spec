"""Module coupling/cohesion scorer and regression ratchet — merge-base scoped."""

from __future__ import annotations

from .audit import CouplingAudit, CouplingAuditError
from .baseline import CouplingBaseline, CouplingBaselineError
from .cli import Cli, Options, main
from .compare import CouplingReview, Row
from .gitio import Diff, GitError, GitRepo
from .graph import ImportGraph
from .imports import ImportResolver
from .layout import PackageLayout
from .metrics import ModuleCouplingMetrics
from .outcome import Outcome
from .packages import PackageMetrics, PackageScorer
from .ratchet import CouplingRatchet
from .report import CouplingReport
from .scorer import CouplingScorer
from .thresholds import CouplingThresholds
from .writer import CouplingWriter

__all__ = [
    "Cli",
    "CouplingAudit",
    "CouplingAuditError",
    "CouplingBaseline",
    "CouplingBaselineError",
    "CouplingRatchet",
    "CouplingReport",
    "CouplingReview",
    "CouplingScorer",
    "CouplingThresholds",
    "CouplingWriter",
    "Diff",
    "GitError",
    "GitRepo",
    "ImportGraph",
    "ImportResolver",
    "ModuleCouplingMetrics",
    "Options",
    "Outcome",
    "PackageLayout",
    "PackageMetrics",
    "PackageScorer",
    "Row",
    "main",
]
