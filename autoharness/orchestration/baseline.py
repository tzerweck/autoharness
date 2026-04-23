"""Baseline orchestration flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autoharness.config.models import ExperimentConfig
from autoharness.reporting.final_report import write_final_report
from autoharness.reporting.summary import write_run_summary
from autoharness.runners.base import SplitRunResult
from autoharness.runners.pytest_runner import run_pytest_split
from autoharness.runners.script_runner import run_script_split
from autoharness.store import (
    append_ledger_event,
    initialize_run_directory,
    initialize_run_state,
)
from autoharness.store.frontier import write_frontier_state
from autoharness.store.writer import write_json, write_text
from autoharness.surfaces.materialize import snapshot_surface_files
from autoharness.validation.base import ValidationResult
from autoharness.validation.script import validate_script
from autoharness.validation.python import validate_python_import


@dataclass(frozen=True)
class BaselineResult:
    run_dir: Path
    candidate_dir: Path
    candidate_id: str
    validation: ValidationResult
    train: SplitRunResult | None = None
    holdout: SplitRunResult | None = None
    scorecard: SplitRunResult | None = None


def run_baseline(config: ExperimentConfig) -> BaselineResult:
    run_dir = initialize_run_directory(config)
    ledger_path = run_dir / "ledger.jsonl"
    candidate_id = "iter_000_baseline"
    candidate_dir = run_dir / "candidates" / candidate_id

    write_json(run_dir / "experiment.json", config.to_dict())
    append_ledger_event(ledger_path, "baseline_created", {"candidate_id": candidate_id})

    surfaces_dir = candidate_dir / "surfaces"
    written_surfaces = snapshot_surface_files(config.surfaces, surfaces_dir)
    write_json(
        candidate_dir / "meta.json",
        {
            "candidate_id": candidate_id,
            "surface_count": len(written_surfaces),
            "surface_paths": [str(path.relative_to(candidate_dir)) for path in written_surfaces],
        },
    )
    write_text(
        candidate_dir / "hypothesis.md",
        "Baseline candidate captured from the declared editable surfaces.",
    )

    validation = _run_validation(config)
    write_json(
        candidate_dir / "validation" / "result.json",
        {
            "ok": validation.ok,
            "message": validation.message,
        },
    )
    append_ledger_event(
        ledger_path,
        "validation_completed",
        {
            "candidate_id": candidate_id,
            "ok": validation.ok,
            "message": validation.message,
        },
    )
    train_result = None
    holdout_result = None
    scorecard_result = None
    if validation.ok:
        train_result = _run_split(config, "train", candidate_dir)
        holdout_result = _run_split(config, "holdout", candidate_dir)
        scorecard_result = _run_split(config, "scorecard", candidate_dir)

    write_frontier_state(
        run_dir,
        champion_candidate_id=candidate_id if validation.ok and train_result else None,
        primary_metric=config.policy.primary_metric,
        keep_top_k_visible_candidates=config.policy.keep_top_k_visible_candidates,
        baseline_validation_ok=validation.ok,
    )
    initialize_run_state(
        run_dir,
        max_iterations=config.max_iterations,
        champion_candidate_id=candidate_id if validation.ok and train_result else "",
        champion_workspace_root=config.workspace_root,
    )
    write_run_summary(run_dir)
    write_final_report(run_dir)

    return BaselineResult(
        run_dir=run_dir,
        candidate_dir=candidate_dir,
        candidate_id=candidate_id,
        validation=validation,
        train=train_result,
        holdout=holdout_result,
        scorecard=scorecard_result,
    )


def _run_validation(config: ExperimentConfig) -> ValidationResult:
    if config.validation.kind == "python_import":
        return validate_python_import(config.workspace_root, config.validation.entrypoint or "")
    if config.validation.kind == "script" and config.validation.script:
        return validate_script(
            config.workspace_root,
            config.validation.script,
            timeout_sec=config.validation.timeout_sec,
        )
    return ValidationResult(False, f"Validation kind '{config.validation.kind}' is not implemented yet.")


def _run_split(
    config: ExperimentConfig,
    split: str,
    candidate_dir: Path,
) -> SplitRunResult | None:
    if config.runner.kind == "pytest":
        result = run_pytest_split(
            config=config,
            split=split,
            workspace_root=config.workspace_root,
            output_dir=candidate_dir / "eval" / split,
        )
    elif config.runner.kind == "script":
        result = run_script_split(
            config=config,
            split=split,
            workspace_root=config.workspace_root,
            output_dir=candidate_dir / "eval" / split,
        )
    else:
        result = None
    if result is None:
        return None

    append_ledger_event(
        candidate_dir.parent.parent / "ledger.jsonl",
        f"{split}_completed",
        {
            "candidate_id": "iter_000_baseline",
            "split": split,
            "n_cases": result.summary.n_cases,
            "n_passed": result.summary.n_passed,
            "mean_score": result.summary.mean_score,
        },
    )
    return result
