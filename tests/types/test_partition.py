"""Tests for punt_zspec.types.partition."""

from __future__ import annotations

from punt_zspec.types import (
    OperationPartitions,
    Partition,
    PartitionReport,
    PartitionStatus,
)


def _partition(pid: int, status: PartitionStatus, branch: int | None) -> Partition:
    return Partition(
        id=pid,
        class_name="c",
        branch=branch,
        status=status,
        inputs={},
        pre_state={},
        post_state={"y": 1} if branch is not None else None,
    )


def test_to_dict_omits_branch_and_post_state_when_none() -> None:
    result = _partition(1, PartitionStatus.rejected, branch=None).to_dict()
    assert "branch" not in result
    assert "postState" not in result


def test_to_dict_includes_branch_and_post_state_when_present() -> None:
    result = _partition(1, PartitionStatus.accepted, branch=2).to_dict()
    assert result["branch"] == 2
    assert result["postState"] == {"y": 1}


def _op(partitions: list[Partition]) -> OperationPartitions:
    return OperationPartitions(
        name="Op",
        kind="delta",
        inputs=[],
        state_vars=[],
        branches=[],
        partitions=partitions,
    )


def test_summary_tallies_by_status() -> None:
    op = _op(
        [
            _partition(1, PartitionStatus.accepted, 0),
            _partition(2, PartitionStatus.accepted, 1),
            _partition(3, PartitionStatus.rejected, None),
            _partition(4, PartitionStatus.pruned, None),
        ]
    )
    assert op.summary == {"total": 4, "accepted": 2, "rejected": 1, "pruned": 1}


def test_report_totals_aggregate_across_operations() -> None:
    op_a = _op([_partition(1, PartitionStatus.accepted, 0)])
    op_b = _op(
        [
            _partition(2, PartitionStatus.accepted, 0),
            _partition(3, PartitionStatus.rejected, None),
        ]
    )
    report = PartitionReport(specification="s", timestamp="t", operations=[op_a, op_b])
    assert (report.total_partitions, report.total_accepted, report.total_rejected) == (
        3,
        2,
        1,
    )
