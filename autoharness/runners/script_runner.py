"""Script runner implementation."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from autoharness.config.models import CaseConfig, ExperimentConfig
from autoharness.runners.base import SplitRunResult
from autoharness.runners.result_parser import parse_split_run_result
from autoharness.store.writer import write_json, write_jsonl, write_text

_FRAMEWORK_ROOT = Path(__file__).resolve().parents[2]


def run_script_split(
    config: ExperimentConfig,
    split: str,
    workspace_root: Path,
    output_dir: Path,
) -> SplitRunResult | None:
    cases = [case for case in config.cases if case.split == split]
    if not cases:
        return None
    script_config = config.runner.script
    if script_config is None:
        return None

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "cases_manifest.json"
    write_json(manifest_path, [_case_to_payload(case) for case in cases])

    result_json_path = output_dir / script_config.result_json_path
    env = _build_script_env(config, workspace_root)
    env["AUTOHARNESS_SPLIT"] = split
    env["AUTOHARNESS_WORKSPACE_ROOT"] = str(workspace_root)
    env["AUTOHARNESS_OUTPUT_DIR"] = str(output_dir)
    env["AUTOHARNESS_CASES_MANIFEST"] = str(manifest_path)
    env["AUTOHARNESS_RESULT_JSON_PATH"] = str(result_json_path)

    completed = subprocess.run(
        script_config.command,
        cwd=config.runner.project_root or workspace_root,
        env=env,
        capture_output=True,
        text=True,
    )
    write_text(output_dir / "stdout.txt", completed.stdout)
    write_text(output_dir / "stderr.txt", completed.stderr)

    payload = {
        "summary": {
            "split": split,
            "n_cases": len(cases),
            "n_passed": 0,
            "mean_score": 0.0,
            "duration_sec": 0.0,
        },
        "cases": [
            {
                "case_id": case.id,
                "split": split,
                "passed": False,
                "score": 0.0,
                "duration_sec": 0.0,
                "metadata": {"error": f"script exited with {completed.returncode}"},
            }
            for case in cases
        ],
    }
    if completed.returncode == 0 and result_json_path.exists():
        payload = json.loads(result_json_path.read_text(encoding="utf-8"))

    result = parse_split_run_result(payload, split)
    write_json(output_dir / "summary.json", result.summary)
    write_jsonl(output_dir / "cases.jsonl", result.cases)
    return result


def _build_script_env(
    config: ExperimentConfig,
    workspace_root: Path,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(config.runner.env)

    pythonpath_parts = [str(workspace_root), str(_FRAMEWORK_ROOT)]
    existing_pythonpath = env.get("PYTHONPATH")
    if existing_pythonpath:
        pythonpath_parts.append(existing_pythonpath)
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    return env


def _case_to_payload(case: CaseConfig) -> dict[str, object]:
    return {
        "id": case.id,
        "runner_ref": case.runner_ref,
        "split": case.split,
        "stratum": case.stratum,
        "weight": case.weight,
        "tags": case.tags,
        "timeout_sec": case.timeout_sec,
        "metadata": case.metadata,
    }
