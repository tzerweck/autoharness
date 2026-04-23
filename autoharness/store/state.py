"""Run-state persistence helpers for resume/restart support."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autoharness.store.writer import write_json
from autoharness.store.query import read_json


def initialize_run_state(
    run_dir: Path,
    *,
    max_iterations: int,
    champion_candidate_id: str,
    champion_workspace_root: Path,
) -> dict[str, Any]:
    state = {
        "status": "running",
        "max_iterations": max_iterations,
        "next_iteration_index": 1,
        "last_completed_iteration": 0,
        "champion_candidate_id": champion_candidate_id,
        "champion_workspace_root": str(champion_workspace_root),
        "active_iteration_index": None,
        "active_candidate_id": None,
    }
    write_run_state(run_dir, state)
    return state


def load_run_state(run_dir: Path) -> dict[str, Any]:
    state_path = run_dir / "state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"Run state file does not exist: {state_path}")
    return read_json(state_path)


def write_run_state(run_dir: Path, state: dict[str, Any]) -> Path:
    state_path = run_dir / "state.json"
    write_json(state_path, state)
    return state_path


def update_run_state(run_dir: Path, **updates: Any) -> dict[str, Any]:
    state = load_run_state(run_dir)
    state.update(updates)
    write_run_state(run_dir, state)
    return state
