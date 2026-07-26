"""Partition analysis report and its constituent partition types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class PartitionStatus(StrEnum):
    """Status of a single test partition."""

    accepted = "accepted"
    rejected = "rejected"
    pruned = "pruned"


@dataclass(frozen=True)
class Partition:
    """A single test partition derived from TTF analysis."""

    id: int
    class_name: str  # "happy-path", "boundary: min input", "rejected", etc.
    branch: int | None  # which behavioral branch, None for rejected/pruned
    status: PartitionStatus
    inputs: dict[str, Any]
    pre_state: dict[str, Any]
    post_state: dict[str, Any] | None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "id": self.id,
            "class": self.class_name,
            "status": self.status.value,
            "inputs": self.inputs,
            "preState": self.pre_state,
            "notes": self.notes,
        }
        if self.branch is not None:
            result["branch"] = self.branch
        if self.post_state is not None:
            result["postState"] = self.post_state
        return result


@dataclass(frozen=True)
class OperationPartitions:
    """Partition analysis for a single Z operation."""

    name: str
    kind: str  # "delta" or "xi"
    inputs: list[dict[str, Any]]  # [{"name": ..., "type": ..., "constraints": [...]}]
    state_vars: list[str]
    branches: list[dict[str, Any]]
    partitions: list[Partition]

    @property
    def summary(self) -> dict[str, int]:
        total = len(self.partitions)
        accepted = sum(
            1 for p in self.partitions if p.status == PartitionStatus.accepted
        )
        rejected = sum(
            1 for p in self.partitions if p.status == PartitionStatus.rejected
        )
        pruned = sum(1 for p in self.partitions if p.status == PartitionStatus.pruned)
        return {
            "total": total,
            "accepted": accepted,
            "rejected": rejected,
            "pruned": pruned,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "inputs": self.inputs,
            "stateVars": self.state_vars,
            "branches": self.branches,
            "partitions": [p.to_dict() for p in self.partitions],
            "summary": self.summary,
        }


@dataclass(frozen=True)
class PartitionReport:
    """Complete partition analysis report."""

    specification: str
    timestamp: str  # ISO 8601
    operations: list[OperationPartitions]

    @property
    def total_partitions(self) -> int:
        return sum(len(op.partitions) for op in self.operations)

    @property
    def total_accepted(self) -> int:
        return sum(
            1
            for op in self.operations
            for p in op.partitions
            if p.status == PartitionStatus.accepted
        )

    @property
    def total_rejected(self) -> int:
        return sum(
            1
            for op in self.operations
            for p in op.partitions
            if p.status == PartitionStatus.rejected
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "specification": self.specification,
            "timestamp": self.timestamp,
            "operations": [op.to_dict() for op in self.operations],
        }
