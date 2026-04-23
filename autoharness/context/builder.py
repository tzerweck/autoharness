"""Context bundle construction helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from autoharness.config.models import ExperimentConfig
from autoharness.store.query import (
    load_candidate_summary,
    load_frontier,
    list_candidate_ids,
    rank_candidate_summaries,
)
from autoharness.store.writer import write_json, write_text


def build_proposer_context(
    config: ExperimentConfig,
    run_dir: Path,
    proposer_workspace: Path,
    editable_relative_paths: list[str],
    champion_candidate_id: str,
) -> None:
    context_dir = proposer_workspace / "context"
    contract_dir = proposer_workspace / "contract"
    context_dir.mkdir(parents=True, exist_ok=True)
    contract_dir.mkdir(parents=True, exist_ok=True)

    frontier = load_frontier(run_dir)
    selected_candidates = _select_context_candidates(
        run_dir,
        champion_candidate_id,
        config.context.max_candidates,
        config.policy.primary_metric,
    )

    write_text(
        context_dir / "experiment_summary.md",
        "\n".join(
            [
                f"# Experiment: {config.name}",
                "",
                f"- Workspace: {config.workspace_root}",
                f"- Champion candidate: {champion_candidate_id}",
                f"- Primary metric: {config.policy.primary_metric}",
                f"- Editable surfaces: {', '.join(config.surfaces)}",
            ]
        ),
    )
    write_json(context_dir / "frontier.json", frontier)
    write_json(
        context_dir / "manifest.json",
        {
            "champion_candidate_id": champion_candidate_id,
            "selected_candidates": selected_candidates,
        },
    )
    _write_candidate_context(run_dir, context_dir, selected_candidates)
    write_json(
        contract_dir / "writable_surfaces.json",
        {
            "editable_relative_paths": editable_relative_paths,
            "rule": "Only modify files under editable/.",
        },
    )
    write_text(
        contract_dir / "instructions.md",
        "\n".join(
            [
                "You are editing an agent harness candidate.",
                "Only modify files under editable/.",
                "Use context/ for experiment metadata and prior frontier state.",
                "Do not assume access to holdout failure details.",
            ]
        ),
    )


def _select_context_candidates(
    run_dir: Path,
    champion_candidate_id: str,
    max_candidates: int,
    primary_metric: str,
) -> list[str]:
    selected: list[str] = []
    if champion_candidate_id:
        selected.append(champion_candidate_id)

    ranked = rank_candidate_summaries(run_dir, primary_metric, limit=max_candidates * 2)
    for summary in ranked:
        candidate_id = summary["candidate_id"]
        if candidate_id in selected:
            continue
        if len(selected) >= max_candidates:
            return selected
        selected.append(candidate_id)

    recent = [
        candidate_id
        for candidate_id in reversed(list_candidate_ids(run_dir))
        if candidate_id not in selected
    ]
    for candidate_id in recent:
        if len(selected) >= max_candidates:
            break
        selected.append(candidate_id)
    return selected


def _write_candidate_context(run_dir: Path, context_dir: Path, candidate_ids: list[str]) -> None:
    candidates_root = context_dir / "prior_candidates"
    candidates_root.mkdir(parents=True, exist_ok=True)
    for candidate_id in candidate_ids:
        candidate_bundle = candidates_root / candidate_id
        candidate_bundle.mkdir(parents=True, exist_ok=True)
        write_json(candidate_bundle / "summary.json", load_candidate_summary(run_dir, candidate_id))

        source_surfaces = run_dir / "candidates" / candidate_id / "surfaces"
        if source_surfaces.exists():
            destination_surfaces = candidate_bundle / "surfaces"
            if destination_surfaces.exists():
                shutil.rmtree(destination_surfaces)
            shutil.copytree(source_surfaces, destination_surfaces)

        diff_path = run_dir / "candidates" / candidate_id / "diffs" / "unified.patch"
        if diff_path.exists():
            shutil.copy2(diff_path, candidate_bundle / "unified.patch")

        train_cases = run_dir / "candidates" / candidate_id / "eval" / "train" / "cases.jsonl"
        if train_cases.exists():
            shutil.copy2(train_cases, candidate_bundle / "train_cases.jsonl")
