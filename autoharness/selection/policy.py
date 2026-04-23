"""Selection policy implementation."""

from __future__ import annotations

from dataclasses import dataclass

from autoharness.config.models import PolicyConfig
from autoharness.runners.base import CaseResult, SplitSummary


@dataclass(frozen=True)
class CandidateStats:
    train: SplitSummary
    holdout: SplitSummary | None
    holdout_cases: list[CaseResult] | None = None
    changed_file_count: int = 0


@dataclass(frozen=True)
class SelectionDecision:
    status: str
    reason: str

    @property
    def promoted(self) -> bool:
        return self.status == "promoted"


def select_candidate(
    *,
    policy: PolicyConfig,
    champion: CandidateStats,
    candidate: CandidateStats,
    holdout_required_now: bool,
    allow_promotion_without_holdout: bool = False,
) -> SelectionDecision:
    champion_train_score = _metric_value(policy.primary_metric, champion.train)
    candidate_train_score = _metric_value(policy.primary_metric, candidate.train)
    train_delta = candidate_train_score - champion_train_score

    if train_delta < 0:
        return SelectionDecision("discarded", "candidate_regressed_on_train")
    if train_delta == 0:
        if policy.prefer_simpler_on_tie and _is_simpler(candidate, champion):
            if holdout_required_now:
                if candidate.holdout is None or champion.holdout is None:
                    return SelectionDecision("discarded", "candidate_missing_holdout")
                holdout_delta = _metric_value(policy.primary_metric, candidate.holdout) - _metric_value(
                    policy.primary_metric, champion.holdout
                )
                if holdout_delta < -policy.max_allowed_holdout_regression:
                    return SelectionDecision("discarded", "candidate_regressed_on_holdout")
                if _guardrail_regressions(policy, champion, candidate) > policy.max_allowed_guardrail_regressions:
                    return SelectionDecision("discarded", "candidate_regressed_on_guardrails")
                return SelectionDecision("promoted", "candidate_tied_but_simpler")
            if allow_promotion_without_holdout:
                return SelectionDecision("promoted", "candidate_tied_but_simpler")
            return SelectionDecision("screened_in", "candidate_tied_but_simpler_pending_holdout")
        return SelectionDecision("discarded", "candidate_tied_champion")

    if train_delta < policy.min_primary_improvement:
        return SelectionDecision("discarded", "candidate_below_train_improvement_threshold")

    if not holdout_required_now:
        if allow_promotion_without_holdout:
            return SelectionDecision("promoted", "candidate_improved_on_train")
        return SelectionDecision("screened_in", "candidate_improved_on_train_pending_holdout")

    if candidate.holdout is None or champion.holdout is None:
        return SelectionDecision("discarded", "candidate_missing_holdout")

    champion_holdout_score = _metric_value(policy.primary_metric, champion.holdout)
    candidate_holdout_score = _metric_value(policy.primary_metric, candidate.holdout)
    holdout_delta = candidate_holdout_score - champion_holdout_score

    if holdout_delta < -policy.max_allowed_holdout_regression:
        return SelectionDecision("discarded", "candidate_regressed_on_holdout")
    if _guardrail_regressions(policy, champion, candidate) > policy.max_allowed_guardrail_regressions:
        return SelectionDecision("discarded", "candidate_regressed_on_guardrails")
    if holdout_delta > 0:
        return SelectionDecision("promoted", "candidate_improved_on_holdout")
    if holdout_delta == 0:
        return SelectionDecision("promoted", "candidate_improved_on_train_without_holdout_regression")
    return SelectionDecision("discarded", "candidate_holdout_within_regression_margin_but_not_preferred")


def _metric_value(primary_metric: str, summary: SplitSummary) -> float:
    if primary_metric == "mean_score":
        return summary.mean_score
    if summary.n_cases == 0:
        return 0.0
    return summary.n_passed / summary.n_cases


def _is_simpler(candidate: CandidateStats, champion: CandidateStats) -> bool:
    candidate_train_latency = candidate.train.duration_sec
    champion_train_latency = champion.train.duration_sec
    if candidate.changed_file_count != champion.changed_file_count:
        return candidate.changed_file_count < champion.changed_file_count
    return candidate_train_latency < champion_train_latency


def _guardrail_regressions(
    policy: PolicyConfig,
    champion: CandidateStats,
    candidate: CandidateStats,
) -> int:
    if policy.guardrail_case_ids_file is None:
        return 0
    if not champion.holdout_cases or not candidate.holdout_cases:
        return 0

    guardrail_case_ids = _load_guardrail_case_ids(policy.guardrail_case_ids_file)
    champion_by_id = {case.case_id: case for case in champion.holdout_cases}
    candidate_by_id = {case.case_id: case for case in candidate.holdout_cases}
    regressions = 0
    for case_id, champion_case in champion_by_id.items():
        if case_id not in candidate_by_id:
            continue
        if not _is_guardrail_case(case_id, guardrail_case_ids):
            continue
        candidate_case = candidate_by_id[case_id]
        if champion_case.score >= 1.0 and candidate_case.score < 1.0:
            regressions += 1
    return regressions


def _load_guardrail_case_ids(path) -> set[str]:
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _is_guardrail_case(case_id: str, guardrail_case_ids: set[str]) -> bool:
    if case_id in guardrail_case_ids:
        return True
    for item in guardrail_case_ids:
        if item.isdigit() and case_id.endswith(f"_{int(item):04d}"):
            return True
    return False
