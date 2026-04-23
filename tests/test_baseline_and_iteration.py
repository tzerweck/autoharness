from __future__ import annotations

import json
import sys
from pathlib import Path

from autoharness.config import load_experiment_config
from autoharness.orchestration.baseline import run_baseline
from autoharness.orchestration.iterate import run_iteration
from autoharness.selection.policy import CandidateStats, select_candidate
from autoharness.runners.base import CaseResult, SplitSummary


def test_baseline_runs_train_and_holdout(tmp_path: Path) -> None:
    config = load_experiment_config(Path("examples/simple_pytest_agent/experiment.toml"))
    config = config.model_copy(update={"output_root": tmp_path / "runs"})

    result = run_baseline(config)

    assert result.validation.ok is True
    assert result.train is not None
    assert result.train.summary.n_cases == 3
    assert result.train.summary.n_passed == 2
    assert result.holdout is not None
    assert result.holdout.summary.n_passed == 1


def test_iteration_promotes_improved_candidate(tmp_path: Path) -> None:
    config = load_experiment_config(Path("examples/simple_pytest_agent/experiment.toml"))
    config = config.model_copy(
        update={
            "output_root": tmp_path / "runs",
            "policy": config.policy.model_copy(update={"holdout_every": 1}),
            "proposer": config.proposer.model_copy(
                update={
                    "command": [
                        sys.executable,
                        str((Path("tests/fixtures/improve_tools.py")).resolve()),
                    ]
                }
            ),
        }
    )

    baseline = run_baseline(config)
    assert baseline.train is not None
    assert baseline.train.summary.n_passed == 2

    iteration = run_iteration(
        config=config,
        run_dir=baseline.run_dir,
        iteration_index=1,
        champion_candidate_id=baseline.candidate_id,
        champion_workspace_root=config.workspace_root,
    )

    assert iteration.validation.ok is True
    assert iteration.train is not None
    assert iteration.train.summary.n_passed == 3
    assert iteration.promoted is True
    diff_path = iteration.candidate_dir / "diffs" / "unified.patch"
    assert diff_path.exists()
    assert "tools.py" in diff_path.read_text(encoding="utf-8")
    proposer_result = (iteration.candidate_dir / "proposer" / "result.json").read_text(encoding="utf-8")
    assert "Added multiply support to MathTool." in proposer_result


def test_iteration_promotes_improved_candidate_in_batch_pytest_mode(tmp_path: Path) -> None:
    config = load_experiment_config(Path("examples/simple_pytest_agent/experiment.toml"))
    runner = config.runner.model_copy(
        update={
            "pytest": config.runner.pytest.model_copy(update={"execution_mode": "batch"})
            if config.runner.pytest
            else None
        }
    )
    config = config.model_copy(
        update={
            "output_root": tmp_path / "runs",
            "runner": runner,
            "policy": config.policy.model_copy(update={"holdout_every": 1}),
            "proposer": config.proposer.model_copy(
                update={
                    "command": [
                        sys.executable,
                        str((Path("tests/fixtures/improve_tools.py")).resolve()),
                    ]
                }
            ),
        }
    )

    baseline = run_baseline(config)
    assert baseline.train is not None
    assert baseline.train.summary.n_passed == 2
    assert (
        baseline.candidate_dir
        / "eval"
        / "train"
        / config.runner.pytest.report_json_path
    ).exists()

    iteration = run_iteration(
        config=config,
        run_dir=baseline.run_dir,
        iteration_index=1,
        champion_candidate_id=baseline.candidate_id,
        champion_workspace_root=config.workspace_root,
    )

    assert iteration.promoted is True
    assert iteration.train is not None
    assert iteration.train.summary.n_passed == 3
    assert (
        iteration.candidate_dir / "eval" / "train" / "cases" / "train.solve_multiply" / "stdout.txt"
    ).exists()


def test_selection_policy_requires_margin_and_prefers_simpler_tie() -> None:
    champion = CandidateStats(
        train=SplitSummary(split="train", n_cases=3, n_passed=2, mean_score=0.6667, duration_sec=2.0),
        holdout=SplitSummary(split="holdout", n_cases=1, n_passed=1, mean_score=1.0, duration_sec=1.0),
        changed_file_count=2,
    )
    candidate = CandidateStats(
        train=SplitSummary(split="train", n_cases=3, n_passed=2, mean_score=0.6667, duration_sec=1.0),
        holdout=SplitSummary(split="holdout", n_cases=1, n_passed=1, mean_score=1.0, duration_sec=1.0),
        changed_file_count=1,
    )
    config = load_experiment_config(Path("examples/simple_pytest_agent/experiment.toml"))
    policy = config.policy.model_copy(update={"min_primary_improvement": 0.0})
    decision = select_candidate(
        policy=policy,
        champion=champion,
        candidate=candidate,
        holdout_required_now=True,
    )
    assert decision.status == "promoted"
    assert decision.reason == "candidate_tied_but_simpler"


def test_selection_policy_blocks_guardrail_regression(tmp_path: Path) -> None:
    guardrails = tmp_path / "guardrails.txt"
    guardrails.write_text("holdout.case_1\n", encoding="utf-8")
    config = load_experiment_config(Path("examples/simple_pytest_agent/experiment.toml"))
    policy = config.policy.model_copy(
        update={
            "guardrail_case_ids_file": guardrails,
            "max_allowed_guardrail_regressions": 0,
        }
    )
    champion = CandidateStats(
        train=SplitSummary(split="train", n_cases=3, n_passed=2, mean_score=0.6667, duration_sec=2.0),
        holdout=SplitSummary(split="holdout", n_cases=2, n_passed=1, mean_score=0.5, duration_sec=1.0),
        holdout_cases=[
            CaseResult(
                case_id="holdout.case_1",
                split="holdout",
                passed=True,
                score=1.0,
                duration_sec=1.0,
            ),
            CaseResult(
                case_id="holdout.case_2",
                split="holdout",
                passed=False,
                score=0.0,
                duration_sec=1.0,
            ),
        ],
    )
    candidate = CandidateStats(
        train=SplitSummary(split="train", n_cases=3, n_passed=3, mean_score=1.0, duration_sec=1.0),
        holdout=SplitSummary(split="holdout", n_cases=2, n_passed=1, mean_score=0.75, duration_sec=1.0),
        holdout_cases=[
            CaseResult(
                case_id="holdout.case_1",
                split="holdout",
                passed=False,
                score=0.5,
                duration_sec=1.0,
            ),
            CaseResult(
                case_id="holdout.case_2",
                split="holdout",
                passed=True,
                score=1.0,
                duration_sec=1.0,
            ),
        ],
    )
    decision = select_candidate(
        policy=policy,
        champion=champion,
        candidate=candidate,
        holdout_required_now=True,
    )
    assert decision.status == "discarded"
    assert decision.reason == "candidate_regressed_on_guardrails"


def test_manual_proposer_promotes_candidate(tmp_path: Path) -> None:
    config = load_experiment_config(Path("examples/simple_pytest_agent/experiment.toml"))
    manual_source_dir = tmp_path / "manual_candidate"
    manual_source_dir.mkdir()
    (manual_source_dir / "tools.py").write_text(
        Path("examples/simple_pytest_agent/tools.py").read_text(encoding="utf-8").replace(
            "        if len(numbers) >= 2:\n            return str(sum(numbers))\n",
            (
                "        lowered = task.lower()\n"
                "        if 'multiply' in lowered and len(numbers) >= 2:\n"
                "            return str(numbers[0] * numbers[1])\n"
                "        if len(numbers) >= 2:\n"
                "            return str(sum(numbers))\n"
            ),
        ),
        encoding="utf-8",
    )
    (manual_source_dir / "contract").mkdir()
    (manual_source_dir / "contract" / "proposer_result.json").write_text(
        '{"notes": "Manual proposer improved tools."}',
        encoding="utf-8",
    )
    config = config.model_copy(
        update={
            "output_root": tmp_path / "runs",
            "policy": config.policy.model_copy(update={"holdout_every": 1}),
            "proposer": config.proposer.model_copy(
                update={
                    "backend": "manual",
                    "manual_source_dir": manual_source_dir,
                    "command": [],
                }
            ),
        }
    )
    baseline = run_baseline(config)
    iteration = run_iteration(
        config=config,
        run_dir=baseline.run_dir,
        iteration_index=1,
        champion_candidate_id=baseline.candidate_id,
        champion_workspace_root=config.workspace_root,
    )
    assert iteration.promoted is True
    proposer_result = (iteration.candidate_dir / "proposer" / "result.json").read_text(encoding="utf-8")
    assert "Manual proposer improved tools." in proposer_result


def test_screened_in_candidate_stays_visible_in_frontier_and_context(tmp_path: Path) -> None:
    config = load_experiment_config(Path("examples/simple_pytest_agent/experiment.toml"))
    config = config.model_copy(
        update={
            "output_root": tmp_path / "runs",
            "policy": config.policy.model_copy(
                update={
                    "holdout_every": 2,
                    "keep_top_k_visible_candidates": 3,
                }
            ),
            "proposer": config.proposer.model_copy(
                update={
                    "command": [
                        sys.executable,
                        str((Path("tests/fixtures/improve_tools.py")).resolve()),
                    ]
                }
            ),
        }
    )

    baseline = run_baseline(config)
    iteration_one = run_iteration(
        config=config,
        run_dir=baseline.run_dir,
        iteration_index=1,
        champion_candidate_id=baseline.candidate_id,
        champion_workspace_root=config.workspace_root,
    )

    assert iteration_one.status == "screened_in"
    frontier_after_first = json.loads((baseline.run_dir / "frontier.json").read_text(encoding="utf-8"))
    frontier_ids = [
        entry["candidate_id"]
        for entry in frontier_after_first.get("frontier_candidates", [])
    ]
    assert baseline.candidate_id in frontier_ids
    assert iteration_one.candidate_id in frontier_ids

    iteration_two = run_iteration(
        config=config,
        run_dir=baseline.run_dir,
        iteration_index=2,
        champion_candidate_id=baseline.candidate_id,
        champion_workspace_root=config.workspace_root,
    )
    manifest = json.loads(
        (
            baseline.run_dir
            / "proposer_sessions"
            / iteration_two.candidate_id
            / "context"
            / "manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert iteration_one.candidate_id in manifest["selected_candidates"]
