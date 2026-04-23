"""Helpers for creating canonical run directories."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from autoharness.config.models import ExperimentConfig


def initialize_run_directory(config: ExperimentConfig) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = config.output_root / f"{config.name}_{timestamp}"
    for relative in (
        Path("reports"),
        Path("proposer_sessions"),
        Path("candidates"),
        Path("context_cache"),
        Path("workspaces"),
    ):
        (run_dir / relative).mkdir(parents=True, exist_ok=True)
    return run_dir
