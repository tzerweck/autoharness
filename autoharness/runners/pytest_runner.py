"""Pytest runner implementation."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from autoharness.config.models import CaseConfig, ExperimentConfig
from autoharness.runners.base import CaseResult, SplitRunResult, SplitSummary
from autoharness.store.writer import write_json, write_jsonl, write_text

_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]


def run_pytest_split(
    config: ExperimentConfig,
    split: str,
    workspace_root: Path,
    output_dir: Path,
) -> SplitRunResult | None:
    cases = [case for case in config.cases if case.split == split]
    if not cases:
        return None

    project_root = _resolve_project_root(config, workspace_root)
    pytest_config = config.runner.pytest
    if pytest_config is not None and pytest_config.execution_mode == "batch":
        result = _run_pytest_split_batch(
            config=config,
            cases=cases,
            split=split,
            project_root=project_root,
            workspace_root=workspace_root,
            output_dir=output_dir,
        )
    else:
        result = _run_pytest_split_per_case(
            config=config,
            cases=cases,
            split=split,
            project_root=project_root,
            workspace_root=workspace_root,
            output_dir=output_dir,
        )

    write_json(output_dir / "summary.json", result.summary)
    write_jsonl(output_dir / "cases.jsonl", result.cases)
    return result


def _run_pytest_split_per_case(
    config: ExperimentConfig,
    cases: list[CaseConfig],
    split: str,
    project_root: Path,
    workspace_root: Path,
    output_dir: Path,
) -> SplitRunResult:
    case_results: list[CaseResult] = []
    split_start = time.perf_counter()
    for case in cases:
        case_results.append(
            _run_pytest_case(
                config=config,
                case=case,
                project_root=project_root,
                workspace_root=workspace_root,
                output_dir=output_dir / "cases" / _safe_name(case.id),
            )
        )

    duration_sec = time.perf_counter() - split_start
    return SplitRunResult(
        summary=_summarize_cases(split, case_results, duration_sec),
        cases=case_results,
    )


def _run_pytest_split_batch(
    config: ExperimentConfig,
    cases: list[CaseConfig],
    split: str,
    project_root: Path,
    workspace_root: Path,
    output_dir: Path,
) -> SplitRunResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    pytest_config = config.runner.pytest
    assert pytest_config is not None

    report_path = output_dir / pytest_config.report_json_path
    env = _build_pytest_env(config, workspace_root, output_dir)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "autoharness.runners.pytest_plugin",
        f"--autoharness-report-path={report_path}",
        *(pytest_config.pytest_args if pytest_config else []),
    ]
    if pytest_config.junit_xml_path:
        command.append(f"--junitxml={output_dir / pytest_config.junit_xml_path}")
    command.extend(case.runner_ref for case in cases)

    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=_split_timeout(cases),
    )
    duration_sec = time.perf_counter() - start

    write_text(output_dir / "stdout.txt", completed.stdout)
    write_text(output_dir / "stderr.txt", completed.stderr)

    report_payload = _load_batch_report(report_path)
    report_results = report_payload.get("results", {})
    case_results = [
        _case_result_from_batch_report(
            case=case,
            case_output_dir=output_dir / "cases" / _safe_name(case.id),
            report_payload=_match_report_payload(report_results, case.runner_ref),
            split_output_dir=output_dir,
            returncode=completed.returncode,
        )
        for case in cases
    ]
    return SplitRunResult(
        summary=_summarize_cases(split, case_results, duration_sec),
        cases=case_results,
    )


def _run_pytest_case(
    config: ExperimentConfig,
    case: CaseConfig,
    project_root: Path,
    workspace_root: Path,
    output_dir: Path,
) -> CaseResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = _build_pytest_env(config, workspace_root, output_dir)
    pytest_config = config.runner.pytest

    command = [
        sys.executable,
        "-m",
        "pytest",
        *(pytest_config.pytest_args if pytest_config else []),
    ]
    if pytest_config and pytest_config.junit_xml_path:
        command.append(f"--junitxml={output_dir / pytest_config.junit_xml_path}")
    command.append(case.runner_ref)

    start = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=project_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=case.timeout_sec,
    )
    duration_sec = time.perf_counter() - start

    write_text(output_dir / "stdout.txt", completed.stdout)
    write_text(output_dir / "stderr.txt", completed.stderr)

    passed = completed.returncode == 0
    return CaseResult(
        case_id=case.id,
        split=case.split,
        passed=passed,
        score=1.0 if passed else 0.0,
        duration_sec=duration_sec,
        metadata={
            "runner_ref": case.runner_ref,
            "returncode": completed.returncode,
            "execution_mode": "per_case",
            "stdout_path": str((output_dir / "stdout.txt").relative_to(output_dir.parent.parent)),
            "stderr_path": str((output_dir / "stderr.txt").relative_to(output_dir.parent.parent)),
        },
    )


def _build_pytest_env(
    config: ExperimentConfig,
    workspace_root: Path,
    output_dir: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(config.runner.env)
    pytest_config = config.runner.pytest
    if pytest_config is not None:
        env[pytest_config.artifact_dir_env] = str(output_dir / "artifacts")
        env[pytest_config.candidate_dir_env] = str(workspace_root)

    pythonpath_parts = [str(workspace_root), str(_FRAMEWORK_ROOT)]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def _load_batch_report(report_path: Path) -> dict[str, object]:
    if not report_path.exists():
        return {}
    return json.loads(report_path.read_text(encoding="utf-8"))


def _match_report_payload(
    report_results: object,
    runner_ref: str,
) -> dict[str, object] | None:
    if not isinstance(report_results, dict):
        return None
    exact = report_results.get(runner_ref)
    if isinstance(exact, dict):
        return exact
    for nodeid, payload in report_results.items():
        if not isinstance(nodeid, str) or not isinstance(payload, dict):
            continue
        if nodeid.endswith(runner_ref):
            return payload
    return None


def _case_result_from_batch_report(
    case: CaseConfig,
    case_output_dir: Path,
    report_payload: dict[str, object] | None,
    split_output_dir: Path,
    returncode: int,
) -> CaseResult:
    case_output_dir.mkdir(parents=True, exist_ok=True)
    if report_payload is None:
        stdout = ""
        stderr = ""
        longrepr = ""
        passed = False
        duration_sec = 0.0
        error = "missing_result_in_pytest_report"
    else:
        stdout = str(report_payload.get("stdout", ""))
        stderr = str(report_payload.get("stderr", ""))
        longrepr = str(report_payload.get("longrepr", ""))
        passed = report_payload.get("outcome") == "passed"
        duration_sec = float(report_payload.get("duration_sec", 0.0))
        error = ""

    write_text(case_output_dir / "stdout.txt", stdout)
    write_text(case_output_dir / "stderr.txt", stderr)
    if longrepr:
        write_text(case_output_dir / "failure.txt", longrepr)

    metadata = {
        "runner_ref": case.runner_ref,
        "returncode": returncode,
        "execution_mode": "batch",
        "stdout_path": str((case_output_dir / "stdout.txt").relative_to(split_output_dir)),
        "stderr_path": str((case_output_dir / "stderr.txt").relative_to(split_output_dir)),
    }
    if longrepr:
        metadata["failure_path"] = str((case_output_dir / "failure.txt").relative_to(split_output_dir))
    if error:
        metadata["error"] = error

    return CaseResult(
        case_id=case.id,
        split=case.split,
        passed=passed,
        score=1.0 if passed else 0.0,
        duration_sec=duration_sec,
        metadata=metadata,
    )


def _split_timeout(cases: list[CaseConfig]) -> float | None:
    timeouts = [case.timeout_sec for case in cases if case.timeout_sec is not None]
    if not timeouts:
        return None
    return float(sum(timeouts))


def _summarize_cases(split: str, case_results: list[CaseResult], duration_sec: float) -> SplitSummary:
    n_cases = len(case_results)
    n_passed = sum(1 for case in case_results if case.passed)
    mean_score = sum(case.score for case in case_results) / n_cases if n_cases else 0.0
    return SplitSummary(
        split=split,
        n_cases=n_cases,
        n_passed=n_passed,
        mean_score=mean_score,
        duration_sec=duration_sec,
    )


def _resolve_project_root(config: ExperimentConfig, workspace_root: Path) -> Path:
    assert config.runner.project_root is not None
    try:
        relative = config.runner.project_root.relative_to(config.workspace_root)
    except ValueError:
        return config.runner.project_root
    return workspace_root / relative


def _safe_name(value: str) -> str:
    safe = []
    for char in value:
        safe.append(char if char.isalnum() or char in ("-", "_", ".") else "_")
    return "".join(safe)
