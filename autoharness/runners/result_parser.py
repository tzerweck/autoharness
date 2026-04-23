"""Runner result parsing helpers."""

from __future__ import annotations

from typing import Any

from autoharness.runners.base import CaseResult, SplitRunResult, SplitSummary


def parse_split_run_result(payload: dict[str, Any], split: str) -> SplitRunResult:
    cases_payload = payload.get("cases", [])
    case_results = [
        CaseResult(
            case_id=str(case["case_id"]),
            split=str(case.get("split", split)),
            passed=bool(case["passed"]),
            score=float(case.get("score", 1.0 if case["passed"] else 0.0)),
            duration_sec=float(case.get("duration_sec", 0.0)),
            metadata=dict(case.get("metadata", {})),
        )
        for case in cases_payload
    ]

    summary_payload = payload.get("summary")
    if summary_payload:
        summary = SplitSummary(
            split=str(summary_payload.get("split", split)),
            n_cases=int(summary_payload["n_cases"]),
            n_passed=int(summary_payload["n_passed"]),
            mean_score=float(summary_payload["mean_score"]),
            duration_sec=float(summary_payload.get("duration_sec", 0.0)),
        )
    else:
        n_cases = len(case_results)
        n_passed = sum(1 for case in case_results if case.passed)
        mean_score = sum(case.score for case in case_results) / n_cases if n_cases else 0.0
        duration_sec = sum(case.duration_sec for case in case_results)
        summary = SplitSummary(
            split=split,
            n_cases=n_cases,
            n_passed=n_passed,
            mean_score=mean_score,
            duration_sec=duration_sec,
        )
    return SplitRunResult(summary=summary, cases=case_results)
