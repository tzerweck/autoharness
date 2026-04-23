"""Frontier state construction helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from autoharness.store.query import load_candidate_summary, rank_candidate_summaries
from autoharness.store.writer import write_json


def write_frontier_state(
    run_dir: Path,
    *,
    champion_candidate_id: str | None,
    primary_metric: str,
    keep_top_k_visible_candidates: int,
    baseline_validation_ok: bool,
) -> dict[str, Any]:
    champion_summary = (
        load_candidate_summary(run_dir, champion_candidate_id)
        if champion_candidate_id
        else {}
    )
    frontier_candidates = _build_frontier_candidates(
        run_dir=run_dir,
        champion_candidate_id=champion_candidate_id,
        primary_metric=primary_metric,
        keep_top_k_visible_candidates=keep_top_k_visible_candidates,
    )
    payload = {
        "champion_candidate_id": champion_candidate_id,
        "baseline_validation_ok": baseline_validation_ok,
        "train_summary": champion_summary.get("train"),
        "holdout_summary": champion_summary.get("holdout"),
        "scorecard_summary": champion_summary.get("scorecard"),
        "frontier_candidates": frontier_candidates,
    }
    write_json(run_dir / "frontier.json", payload)
    return payload


def _build_frontier_candidates(
    *,
    run_dir: Path,
    champion_candidate_id: str | None,
    primary_metric: str,
    keep_top_k_visible_candidates: int,
) -> list[dict[str, Any]]:
    ranked = rank_candidate_summaries(
        run_dir,
        primary_metric=primary_metric,
        limit=max(keep_top_k_visible_candidates * 2, keep_top_k_visible_candidates),
    )
    selected_ids: list[str] = []
    selected: list[dict[str, Any]] = []

    if champion_candidate_id:
        champion_entry = next(
            (summary for summary in ranked if summary["candidate_id"] == champion_candidate_id),
            None,
        )
        if champion_entry is None:
            champion_entry = load_candidate_summary(run_dir, champion_candidate_id)
            champion_entry = {
                **champion_entry,
                "train_metric": _summary_metric(primary_metric, champion_entry.get("train")),
                "holdout_metric": _summary_metric(primary_metric, champion_entry.get("holdout")),
            }
        selected_ids.append(champion_candidate_id)
        selected.append(_frontier_candidate_payload(champion_entry))

    for summary in ranked:
        candidate_id = summary["candidate_id"]
        if candidate_id in selected_ids:
            continue
        if len(selected) >= keep_top_k_visible_candidates:
            break
        selected_ids.append(candidate_id)
        selected.append(_frontier_candidate_payload(summary))
    return selected


def _frontier_candidate_payload(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": summary["candidate_id"],
        "decision": summary.get("decision"),
        "validation_ok": bool((summary.get("validation") or {}).get("ok")),
        "train_metric": summary.get("train_metric", 0.0),
        "holdout_metric": summary.get("holdout_metric", 0.0),
        "train_summary": summary.get("train"),
        "holdout_summary": summary.get("holdout"),
        "scorecard_summary": summary.get("scorecard"),
    }


def _summary_metric(primary_metric: str, summary: dict[str, Any] | None) -> float:
    if not summary:
        return 0.0
    if primary_metric == "mean_score":
        return float(summary.get("mean_score", 0.0))
    n_cases = int(summary.get("n_cases", 0))
    if n_cases == 0:
        return 0.0
    return float(summary.get("n_passed", 0)) / n_cases
