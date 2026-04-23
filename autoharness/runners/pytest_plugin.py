"""Pytest plugin used for batch split reporting."""

from __future__ import annotations

import json
from pathlib import Path

_RESULTS: dict[str, dict[str, object]] = {}


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--autoharness-report-path",
        action="store",
        default=None,
        help="Write machine-readable case results for autoharness to this JSON file.",
    )


def pytest_configure(config) -> None:
    global _RESULTS
    _RESULTS = {}


def pytest_runtest_logreport(report) -> None:
    global _RESULTS
    if report.when != "call":
        return

    _RESULTS[report.nodeid] = {
        "nodeid": report.nodeid,
        "outcome": report.outcome,
        "duration_sec": getattr(report, "duration", 0.0),
        "stdout": getattr(report, "capstdout", ""),
        "stderr": getattr(report, "capstderr", ""),
        "longrepr": getattr(report, "longreprtext", ""),
    }


def pytest_sessionfinish(session, exitstatus) -> None:
    report_path = session.config.getoption("autoharness_report_path")
    if not report_path:
        return

    payload = {
        "exitstatus": exitstatus,
        "results": _RESULTS,
    }
    output_path = Path(report_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
