"""Finalization orchestration helpers."""

from __future__ import annotations

from pathlib import Path

from autoharness.reporting.final_report import write_final_report
from autoharness.reporting.summary import write_run_summary
from autoharness.store import load_run_state, write_run_state


def finalize_run(run_dir: Path, *, max_iterations: int) -> dict[str, object]:
    state = load_run_state(run_dir)
    state["status"] = "completed"
    state["max_iterations"] = max_iterations
    state["active_iteration_index"] = None
    state["active_candidate_id"] = None
    write_run_state(run_dir, state)
    write_run_summary(run_dir)
    write_final_report(run_dir)
    return state
