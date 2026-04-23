"""Store query helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autoharness.runners.base import CaseResult, SplitSummary


def latest_run_dir(output_root: Path, experiment_name: str | None = None) -> Path | None:
    if not output_root.exists():
        return None
    candidates = [path for path in output_root.iterdir() if path.is_dir()]
    if experiment_name is not None:
        prefix = f"{experiment_name}_"
        candidates = [path for path in candidates if path.name.startswith(prefix)]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.name)[-1]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[Any]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def load_frontier(run_dir: Path) -> dict[str, Any]:
    frontier_path = run_dir / "frontier.json"
    if not frontier_path.exists():
        return {}
    return read_json(frontier_path)


def list_candidate_ids(run_dir: Path) -> list[str]:
    candidates_dir = run_dir / "candidates"
    if not candidates_dir.exists():
        return []
    return sorted(path.name for path in candidates_dir.iterdir() if path.is_dir())


def load_candidate_summary(run_dir: Path, candidate_id: str) -> dict[str, Any]:
    candidate_dir = run_dir / "candidates" / candidate_id
    summary: dict[str, Any] = {"candidate_id": candidate_id}
    validation_path = candidate_dir / "validation" / "result.json"
    if validation_path.exists():
        summary["validation"] = read_json(validation_path)

    for split in ("train", "holdout", "scorecard"):
        split_summary_path = candidate_dir / "eval" / split / "summary.json"
        if split_summary_path.exists():
            summary[split] = read_json(split_summary_path)

    proposer_path = candidate_dir / "proposer" / "result.json"
    if proposer_path.exists():
        summary["proposer"] = read_json(proposer_path)

    meta_path = candidate_dir / "meta.json"
    if meta_path.exists():
        summary["meta"] = read_json(meta_path)

    summary["decision"] = load_candidate_decision(run_dir, candidate_id)
    return summary


def load_candidate_decision(run_dir: Path, candidate_id: str) -> dict[str, Any] | None:
    ledger_path = run_dir / "ledger.jsonl"
    if not ledger_path.exists():
        return None
    events = read_jsonl(ledger_path)
    for event in reversed(events):
        payload = event.get("payload", {})
        if payload.get("candidate_id") != candidate_id:
            continue
        if event.get("event_type") in {
            "candidate_promoted",
            "candidate_discarded",
            "candidate_screened_in",
        }:
            return {"event_type": event["event_type"], **payload}
    return None


def list_candidate_summaries(run_dir: Path) -> list[dict[str, Any]]:
    return [load_candidate_summary(run_dir, candidate_id) for candidate_id in list_candidate_ids(run_dir)]


def rank_candidate_summaries(
    run_dir: Path,
    primary_metric: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    ranked = []
    for summary in list_candidate_summaries(run_dir):
        train_metric = _metric_value(primary_metric, summary.get("train"))
        holdout_metric = _metric_value(primary_metric, summary.get("holdout"))
        ranked.append(
            {
                **summary,
                "train_metric": train_metric,
                "holdout_metric": holdout_metric,
                "decision_rank": _decision_rank(summary),
            }
        )

    ranked.sort(
        key=lambda item: (
            item["decision_rank"],
            bool((item.get("validation") or {}).get("ok")),
            item["train_metric"],
            item["holdout_metric"],
            item["candidate_id"],
        ),
        reverse=True,
    )
    return ranked[:limit]


def load_split_summary(run_dir: Path, candidate_id: str, split: str) -> SplitSummary | None:
    summary_path = run_dir / "candidates" / candidate_id / "eval" / split / "summary.json"
    if not summary_path.exists():
        return None
    return SplitSummary(**read_json(summary_path))


def load_split_cases(run_dir: Path, candidate_id: str, split: str) -> list[CaseResult]:
    cases_path = run_dir / "candidates" / candidate_id / "eval" / split / "cases.jsonl"
    if not cases_path.exists():
        return []
    return [CaseResult(**row) for row in read_jsonl(cases_path)]


def load_run_state_if_present(run_dir: Path) -> dict[str, Any] | None:
    state_path = run_dir / "state.json"
    if not state_path.exists():
        return None
    return read_json(state_path)


def _metric_value(primary_metric: str, summary: dict[str, Any] | None) -> float:
    if not summary:
        return 0.0
    if primary_metric == "mean_score":
        return float(summary.get("mean_score", 0.0))
    n_cases = int(summary.get("n_cases", 0))
    if n_cases == 0:
        return 0.0
    return float(summary.get("n_passed", 0)) / n_cases


def _decision_rank(summary: dict[str, Any]) -> int:
    decision = (summary.get("decision") or {}).get("event_type")
    if decision == "candidate_promoted":
        return 3
    if decision == "candidate_screened_in":
        return 2
    if decision == "candidate_discarded":
        return 1
    return 0
