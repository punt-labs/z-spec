"""Humble-object tests for DoctorCommand — injected resolvers, no PATH lookup."""

from __future__ import annotations

from pathlib import Path

from punt_zspec import __version__
from punt_zspec.commands.doctor import DoctorCommand, DoctorReport


def test_doctor_reports_both_binaries_present() -> None:
    cmd = DoctorCommand(
        fuzz=lambda: Path("/bin/fuzz"),
        probcli=lambda: Path("/bin/probcli"),
    )

    health = cmd.run().unwrap()

    assert health.version == __version__
    assert health.fuzz == Path("/bin/fuzz")
    assert health.probcli == Path("/bin/probcli")
    assert health.healthy


def test_doctor_is_unhealthy_when_a_binary_is_absent() -> None:
    cmd = DoctorCommand(fuzz=lambda: Path("/bin/fuzz"), probcli=lambda: None)

    health = cmd.run().unwrap()

    assert not health.healthy
    assert health.probcli is None


def test_doctor_result_is_always_ok() -> None:
    cmd = DoctorCommand(fuzz=lambda: None, probcli=lambda: None)

    result = cmd.run()

    assert result.is_ok
    assert result.error is None


def test_doctor_report_serializes_present_binaries() -> None:
    report = DoctorReport(
        version="9.9.9", fuzz=Path("/bin/fuzz"), probcli=Path("/bin/probcli")
    )

    assert report.to_dict() == {
        "version": "9.9.9",
        "fuzz": "/bin/fuzz",
        "probcli": "/bin/probcli",
        "healthy": True,
    }


def test_doctor_report_serializes_absent_binaries() -> None:
    report = DoctorReport(version="9.9.9", fuzz=None, probcli=None)

    assert report.to_dict() == {
        "version": "9.9.9",
        "fuzz": None,
        "probcli": None,
        "healthy": False,
    }
