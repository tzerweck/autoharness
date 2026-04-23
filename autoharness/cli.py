"""CLI entrypoint for the framework."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Sequence

from autoharness.config import load_experiment_config, load_saved_experiment_config
from autoharness.errors import AutoharnessError, NotImplementedYetError
from autoharness.orchestration.baseline import run_baseline
from autoharness.orchestration.finalize import finalize_run
from autoharness.orchestration.iterate import run_iteration
from autoharness.reporting.final_report import write_final_report
from autoharness.reporting.summary import write_run_summary
from autoharness.store import load_run_state, update_run_state, write_run_state
from autoharness.store.query import (
    latest_run_dir,
    list_candidate_summaries,
    load_frontier,
    load_run_state_if_present,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="autoharness",
        description="Framework for evolving agent harnesses through iterative evaluation.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate-config",
        help="Validate and normalize an experiment config.",
    )
    validate_parser.add_argument("config", help="Path to the experiment TOML file.")
    validate_parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the normalized config as JSON.",
    )
    validate_parser.set_defaults(func=_cmd_validate_config)

    baseline_parser = subparsers.add_parser(
        "baseline",
        help="Materialize the baseline candidate and run validation.",
    )
    baseline_parser.add_argument(
        "--config",
        required=True,
        help="Path to the experiment TOML file.",
    )
    baseline_parser.set_defaults(func=_cmd_baseline)

    for name, help_text in (
        ("report", "Render reports for an existing run."),
        ("inspect", "Inspect frontier and candidate state for an existing run."),
    ):
        subparser = subparsers.add_parser(name, help=help_text)
        subparser.add_argument(
            "--config",
            required=False,
            help="Path to the experiment TOML file where applicable.",
        )
        subparser.add_argument(
            "--run-dir",
            required=False,
            help="Path to an existing run directory. Overrides --config if provided.",
        )
        subparser.set_defaults(
            func=_cmd_report if name == "report" else _cmd_inspect,
            command_name=name,
        )

    run_parser = subparsers.add_parser(
        "run",
        help="Run the baseline plus a small automated optimization loop.",
    )
    run_parser.add_argument(
        "--config",
        required=False,
        help="Path to the experiment TOML file.",
    )
    run_parser.add_argument(
        "--run-dir",
        required=False,
        help="Resume a specific run directory instead of starting a new run.",
    )
    run_parser.add_argument(
        "--iterations",
        type=int,
        default=None,
        help="Override the configured max iteration count.",
    )
    run_parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume the latest matching run instead of starting a fresh run.",
    )
    run_parser.set_defaults(func=_cmd_run)

    return parser


def _cmd_validate_config(args: argparse.Namespace) -> int:
    config = load_experiment_config(Path(args.config))
    if args.json:
        print(json.dumps(config.to_dict(), indent=2, sort_keys=True))
        return 0

    print(f"Config: {args.config}")
    print(f"Name: {config.name}")
    print(f"Workspace: {config.workspace_root}")
    print(f"Output root: {config.output_root}")
    print(f"Runner: {config.runner.kind}")
    print(f"Proposer: {config.proposer.backend}")
    print(f"Surfaces: {', '.join(config.surfaces)}")
    split_counts: dict[str, int] = {}
    for case in config.cases:
        split_counts[case.split] = split_counts.get(case.split, 0) + 1
    print(f"Cases: {split_counts}")
    print("Status: OK")
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    config = load_experiment_config(Path(args.config))
    result = run_baseline(config)
    print(f"Run directory: {result.run_dir}")
    print(f"Candidate: {result.candidate_id}")
    print(f"Validation: {'ok' if result.validation.ok else 'failed'}")
    print(f"Message: {result.validation.message}")
    if result.train:
        print(
            f"Train: {result.train.summary.n_passed}/{result.train.summary.n_cases} "
            f"passed, mean_score={result.train.summary.mean_score:.3f}"
        )
    if result.holdout:
        print(
            f"Holdout: {result.holdout.summary.n_passed}/{result.holdout.summary.n_cases} "
            f"passed, mean_score={result.holdout.summary.mean_score:.3f}"
        )
    if result.scorecard:
        print(
            f"Scorecard: {result.scorecard.summary.n_passed}/{result.scorecard.summary.n_cases} "
            f"passed, mean_score={result.scorecard.summary.mean_score:.3f}"
        )
    return 0 if result.validation.ok else 2


def _cmd_run(args: argparse.Namespace) -> int:
    config, run_dir, champion_candidate_id, champion_workspace_root, start_iteration, champion_changed_file_count = _prepare_run(
        args
    )

    if run_dir is None:
        baseline = run_baseline(config)
        run_dir = baseline.run_dir
        print(f"Baseline run directory: {baseline.run_dir}")
        if not baseline.validation.ok or baseline.train is None:
            print("Baseline failed before iterative optimization could start.")
            return 2
        champion_candidate_id = baseline.candidate_id
        champion_workspace_root = config.workspace_root
        start_iteration = 1
        champion_changed_file_count = 0
    else:
        print(f"Resuming run directory: {run_dir}")

    assert run_dir is not None
    max_iterations = config.max_iterations
    for iteration_index in range(start_iteration, max_iterations + 1):
        candidate_id = f"iter_{iteration_index:03d}_cand_a"
        update_run_state(
            run_dir,
            status="running",
            max_iterations=max_iterations,
            active_iteration_index=iteration_index,
            active_candidate_id=candidate_id,
        )
        iteration = run_iteration(
            config=config,
            run_dir=run_dir,
            iteration_index=iteration_index,
            champion_candidate_id=champion_candidate_id,
            champion_workspace_root=champion_workspace_root,
            champion_changed_file_count=champion_changed_file_count,
        )
        print(
            f"Iteration {iteration_index}: {iteration.candidate_id} "
            f"{iteration.status} ({iteration.reason})"
        )
        if iteration.promoted:
            champion_candidate_id = iteration.candidate_id
            champion_workspace_root = iteration.candidate_workspace
            champion_changed_file_count = _candidate_changed_file_count(run_dir, iteration.candidate_id)
        update_run_state(
            run_dir,
            status="running",
            max_iterations=max_iterations,
            last_completed_iteration=iteration_index,
            next_iteration_index=iteration_index + 1,
            champion_candidate_id=champion_candidate_id,
            champion_workspace_root=str(champion_workspace_root),
            active_iteration_index=None,
            active_candidate_id=None,
        )

    finalize_run(run_dir, max_iterations=max_iterations)
    print(f"Final champion: {champion_candidate_id}")
    print(f"Run directory: {run_dir}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    run_dir = _resolve_run_dir(args)
    summary_path = write_run_summary(run_dir)
    final_path = write_final_report(run_dir)
    print(f"Summary report: {summary_path}")
    print(f"Final report: {final_path}")
    return 0


def _cmd_inspect(args: argparse.Namespace) -> int:
    run_dir = _resolve_run_dir(args)
    frontier = load_frontier(run_dir)
    print(f"Run directory: {run_dir}")
    print(f"Champion: {frontier.get('champion_candidate_id')}")
    for summary in list_candidate_summaries(run_dir):
        decision = summary.get("decision") or {}
        validation = summary.get("validation") or {}
        train = summary.get("train")
        line = f"- {summary['candidate_id']}: validation={'ok' if validation.get('ok') else 'failed'}"
        if train:
            line += f", train={train.get('n_passed')}/{train.get('n_cases')}"
        if decision:
            line += f", decision={decision.get('event_type')}({decision.get('reason')})"
        print(line)
    return 0


def _cmd_not_implemented(args: argparse.Namespace) -> int:
    raise NotImplementedYetError(
        f"The '{args.command_name}' command is scaffolded but not implemented yet."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except AutoharnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _resolve_run_dir(args: argparse.Namespace) -> Path:
    if getattr(args, "run_dir", None):
        return Path(args.run_dir).expanduser().resolve()
    if getattr(args, "config", None):
        config = load_experiment_config(Path(args.config))
        run_dir = latest_run_dir(config.output_root, config.name)
        if run_dir is None:
            raise AutoharnessError(
                f"No run directories found under {config.output_root} for experiment {config.name}."
            )
        return run_dir
    raise AutoharnessError("Expected either --run-dir or --config.")


def _prepare_run(
    args: argparse.Namespace,
) -> tuple[
    object,
    Path | None,
    str,
    Path,
    int,
    int,
]:
    if args.run_dir:
        run_dir = Path(args.run_dir).expanduser().resolve()
        config = load_saved_experiment_config(run_dir / "experiment.json")
    elif args.config:
        config = load_experiment_config(Path(args.config))
        run_dir = None
    else:
        raise AutoharnessError("Expected --config or --run-dir.")

    if args.iterations is not None:
        config = config.model_copy(update={"max_iterations": args.iterations})

    if not args.resume and args.run_dir is None:
        return config, None, "", config.workspace_root, 1, 0

    if run_dir is None:
        run_dir = latest_run_dir(config.output_root, config.name)
        if run_dir is None:
            raise AutoharnessError(
                f"No run directories found under {config.output_root} for experiment {config.name}."
            )

    state = load_run_state_if_present(run_dir)
    if state is None:
        raise AutoharnessError(f"No state.json found for run directory: {run_dir}")

    if config.max_iterations > state.get("max_iterations", 0):
        state["status"] = "running"
        state["max_iterations"] = config.max_iterations
        write_run_state(run_dir, state)

    active_iteration = state.get("active_iteration_index")
    active_candidate_id = state.get("active_candidate_id")
    if active_iteration is not None:
        _cleanup_partial_iteration(run_dir, int(active_iteration), str(active_candidate_id or ""))
        state["active_iteration_index"] = None
        state["active_candidate_id"] = None
        state["next_iteration_index"] = int(active_iteration)
        state["status"] = "running"
        write_run_state(run_dir, state)

    next_iteration = int(state.get("next_iteration_index", 1))
    champion_candidate_id = str(state.get("champion_candidate_id", "iter_000_baseline"))
    champion_workspace_root = Path(state.get("champion_workspace_root", str(config.workspace_root)))
    champion_changed_file_count = _candidate_changed_file_count(run_dir, champion_candidate_id)
    return (
        config,
        run_dir,
        champion_candidate_id,
        champion_workspace_root,
        next_iteration,
        champion_changed_file_count,
    )


def _candidate_changed_file_count(run_dir: Path, candidate_id: str) -> int:
    candidate_summary = next(
        (summary for summary in list_candidate_summaries(run_dir) if summary["candidate_id"] == candidate_id),
        None,
    )
    if not candidate_summary:
        return 0
    proposer = candidate_summary.get("proposer") or {}
    changed_files = proposer.get("changed_files") or []
    return len(changed_files)


def _cleanup_partial_iteration(run_dir: Path, iteration_index: int, candidate_id: str) -> None:
    if not candidate_id:
        candidate_id = f"iter_{iteration_index:03d}_cand_a"
    for root in ("candidates", "proposer_sessions", "workspaces"):
        path = run_dir / root / candidate_id
        if path.exists():
            shutil.rmtree(path)


if __name__ == "__main__":
    raise SystemExit(main())
