"""Parameter bundles for the probcli-backed commands."""

from __future__ import annotations

from dataclasses import dataclass
from typing import final


@final
@dataclass(frozen=True, slots=True)
class ProbOptions:
    """Tuning knobs shared by the model-check and full-suite commands."""

    setsize: int = 2
    max_ops: int = 1000
    timeout_ms: int = 30000


@final
@dataclass(frozen=True, slots=True)
class AnimateOptions:
    """Tuning knobs for the animate command."""

    steps: int = 20
    setsize: int = 2
