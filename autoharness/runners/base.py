"""Base result structures for runners."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    split: str
    passed: bool
    score: float
    duration_sec: float
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SplitSummary:
    split: str
    n_cases: int
    n_passed: int
    mean_score: float
    duration_sec: float


@dataclass(frozen=True)
class SplitRunResult:
    summary: SplitSummary
    cases: list[CaseResult] = field(default_factory=list)
