"""OO quality scorer and baseline ratchet — merge-base comparison in CI."""

from __future__ import annotations

from .apply import PlanApplier, UpdatePlan
from .audit import AuditError, AuditLog
from .baseline import Baseline, BaselineError
from .cli import Cli, Options, main
from .compare import FileReview, Review, Row
from .gitio import Diff, GitError, GitRepo
from .metrics import ModuleMetrics
from .outcome import Outcome
from .ratchet import Ratchet
from .scorer import Scorer
from .thresholds import Thresholds
from .writer import BaselineWriter

__all__ = [
    "AuditError",
    "AuditLog",
    "Baseline",
    "BaselineError",
    "BaselineWriter",
    "Cli",
    "Diff",
    "FileReview",
    "GitError",
    "GitRepo",
    "ModuleMetrics",
    "Options",
    "Outcome",
    "PlanApplier",
    "Ratchet",
    "Review",
    "Row",
    "Scorer",
    "Thresholds",
    "UpdatePlan",
    "main",
]
