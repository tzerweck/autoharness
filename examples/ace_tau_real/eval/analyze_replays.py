"""Summarize repeated replay results and compute an observed noise floor."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _load_run(path: Path) -> tuple[float, dict[str, float]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload["summary"]
    case_scores = {
        case["case_id"]: float(case["score"])
        for case in payload.get("cases", [])
    }
    return float(summary["mean_score"]), case_scores


def _resolve_focus_case_ids(manifest_path: Path, all_case_ids: set[str]) -> list[str]:
    requested = [
        line.strip()
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matched: set[str] = set()
    for item in requested:
        if item in all_case_ids:
            matched.add(item)
            continue
        if item.isdigit():
            suffix = f"_{int(item):04d}"
            matched.update(case_id for case_id in all_case_ids if case_id.endswith(suffix))
    return sorted(matched)


def _case_instability_report(
    runs: list[tuple[str, float, dict[str, float]]],
    case_ids: set[str],
) -> dict[str, object]:
    pairwise_case_mean_deltas: list[float] = []
    pairwise_case_max_deltas: list[float] = []
    unstable_case_ids: set[str] = set()

    for index, (_, _, left_scores) in enumerate(runs):
        for _, _, right_scores in runs[index + 1 :]:
            case_deltas: list[float] = []
            for case_id in sorted(case_ids):
                left_score = left_scores.get(case_id)
                right_score = right_scores.get(case_id)
                if left_score is None or right_score is None:
                    continue
                delta = abs(left_score - right_score)
                case_deltas.append(delta)
                if delta > 0.0:
                    unstable_case_ids.add(case_id)
            if case_deltas:
                pairwise_case_mean_deltas.append(sum(case_deltas) / len(case_deltas))
                pairwise_case_max_deltas.append(max(case_deltas))

    return {
        "pairwise_case_mean_abs_deltas": pairwise_case_mean_deltas,
        "observed_case_noise_floor": (
            max(pairwise_case_mean_deltas) if pairwise_case_mean_deltas else 0.0
        ),
        "max_single_case_delta": (
            max(pairwise_case_max_deltas) if pairwise_case_max_deltas else 0.0
        ),
        "unstable_case_count": len(unstable_case_ids),
        "unstable_cases": sorted(unstable_case_ids),
    }


def _mean_report(
    runs: list[tuple[str, float, dict[str, float]]],
    focus_case_ids: set[str] | None = None,
) -> dict[str, object]:
    mean_scores: list[dict[str, object]] = []
    scores: list[float] = []
    for path, score, case_scores in runs:
        if focus_case_ids is None:
            mean = score
        else:
            selected = [
                case_score
                for case_id, case_score in case_scores.items()
                if case_id in focus_case_ids
            ]
            if not selected:
                continue
            mean = sum(selected) / len(selected)
        mean_scores.append({"path": path, "mean_score": mean})
        scores.append(mean)

    if len(scores) < 2:
        return {
            "mean_scores": mean_scores,
            "mean_of_means": scores[0] if scores else None,
            "stddev_mean_score": 0.0,
            "pairwise_abs_deltas": [],
            "observed_noise_floor": 0.0,
            "recommended_delta": 0.05,
        }

    pairwise_deltas: list[float] = []
    for index, left in enumerate(scores):
        for right in scores[index + 1 :]:
            pairwise_deltas.append(abs(left - right))

    average = sum(scores) / len(scores)
    variance = sum((score - average) ** 2 for score in scores) / len(scores)
    stddev = math.sqrt(variance)

    return {
        "mean_scores": mean_scores,
        "mean_of_means": average,
        "stddev_mean_score": stddev,
        "pairwise_abs_deltas": pairwise_deltas,
        "observed_noise_floor": max(pairwise_deltas),
        "recommended_delta": max(0.05, max(pairwise_deltas)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("results", nargs="+", help="Paths to replay result.json files.")
    parser.add_argument(
        "--focus-manifest",
        help="Optional file containing task IDs or exact case IDs to analyze separately.",
    )
    args = parser.parse_args()

    runs: list[tuple[str, float, dict[str, float]]] = []
    for item in args.results:
        path = Path(item).expanduser().resolve()
        mean_score, case_scores = _load_run(path)
        runs.append((str(path), mean_score, case_scores))

    if len(runs) < 2:
        raise SystemExit("Need at least two replay results to estimate a noise floor.")

    all_case_ids = {
        case_id
        for _, _, case_scores in runs
        for case_id in case_scores
    }
    case_report = _case_instability_report(runs, all_case_ids)
    mean_report = _mean_report(runs)

    report = {
        "n_runs": len(runs),
        **mean_report,
        **case_report,
    }
    if args.focus_manifest:
        focus_case_ids = _resolve_focus_case_ids(
            Path(args.focus_manifest).expanduser().resolve(),
            all_case_ids,
        )
        report["focus_manifest"] = {
            "path": str(Path(args.focus_manifest).expanduser().resolve()),
            "matched_case_ids": focus_case_ids,
            **_mean_report(runs, set(focus_case_ids)),
            **_case_instability_report(runs, set(focus_case_ids)),
        }
    print(json.dumps(report, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
