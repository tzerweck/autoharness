"""Run summary generation helpers."""

from __future__ import annotations

from pathlib import Path

from autoharness.store.query import load_frontier, list_candidate_summaries
from autoharness.store.writer import write_text


def render_run_summary(run_dir: Path) -> str:
    frontier = load_frontier(run_dir)
    candidate_summaries = list_candidate_summaries(run_dir)
    lines = [
        f"# Run Summary: {run_dir.name}",
        "",
        f"- Champion candidate: {frontier.get('champion_candidate_id')}",
    ]
    train_summary = frontier.get("train_summary")
    if train_summary:
        lines.append(
            f"- Champion train: {train_summary.get('n_passed')}/{train_summary.get('n_cases')} "
            f"passed, mean_score={train_summary.get('mean_score'):.3f}"
        )
    holdout_summary = frontier.get("holdout_summary")
    if holdout_summary:
        lines.append(
            f"- Champion holdout: {holdout_summary.get('n_passed')}/{holdout_summary.get('n_cases')} "
            f"passed, mean_score={holdout_summary.get('mean_score'):.3f}"
        )
    frontier_candidates = frontier.get("frontier_candidates") or []
    if frontier_candidates:
        lines.extend(["", "## Frontier", ""])
        for entry in frontier_candidates:
            decision = entry.get("decision") or {}
            train = entry.get("train_summary")
            holdout = entry.get("holdout_summary")
            lines.append(f"### {entry.get('candidate_id')}")
            if train:
                lines.append(
                    f"- Train: {train.get('n_passed')}/{train.get('n_cases')} "
                    f"passed, mean_score={train.get('mean_score'):.3f}"
                )
            if holdout:
                lines.append(
                    f"- Holdout: {holdout.get('n_passed')}/{holdout.get('n_cases')} "
                    f"passed, mean_score={holdout.get('mean_score'):.3f}"
                )
            if decision:
                lines.append(
                    f"- Frontier status: {decision.get('event_type')} ({decision.get('reason')})"
                )
            lines.append("")
    lines.extend(["", "## Candidates", ""])
    for summary in candidate_summaries:
        decision = summary.get("decision") or {}
        validation = summary.get("validation") or {}
        train = summary.get("train")
        holdout = summary.get("holdout")
        lines.append(f"### {summary['candidate_id']}")
        lines.append(f"- Validation: {'ok' if validation.get('ok') else 'failed'}")
        if train:
            lines.append(
                f"- Train: {train.get('n_passed')}/{train.get('n_cases')} "
                f"passed, mean_score={train.get('mean_score'):.3f}"
            )
        if holdout:
            lines.append(
                f"- Holdout: {holdout.get('n_passed')}/{holdout.get('n_cases')} "
                f"passed, mean_score={holdout.get('mean_score'):.3f}"
            )
        if decision:
            lines.append(f"- Decision: {decision.get('event_type')} ({decision.get('reason')})")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_run_summary(run_dir: Path) -> Path:
    output_path = run_dir / "reports" / "summary.md"
    write_text(output_path, render_run_summary(run_dir))
    return output_path
