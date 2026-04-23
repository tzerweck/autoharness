"""AutoHarness script-runner adapter for fixed-task tau2 airline evaluations."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from autoharness.integrations.tau2 import (
    load_autoharness_case_manifest,
    resolve_tau2_root,
    resolve_tau2_python_command,
)


def main() -> int:
    env = os.environ
    workspace_root = Path(env["AUTOHARNESS_WORKSPACE_ROOT"]).resolve()
    output_dir = Path(env["AUTOHARNESS_OUTPUT_DIR"]).resolve()
    manifest_path = Path(env["AUTOHARNESS_CASES_MANIFEST"]).resolve()
    result_json_path = Path(env["AUTOHARNESS_RESULT_JSON_PATH"]).resolve()

    tau2_root = resolve_tau2_root(workspace_root, env)
    cases = load_autoharness_case_manifest(manifest_path)
    repo_root = Path(__file__).resolve().parents[3]
    harness_bundle = _load_harness_bundle(workspace_root)
    bundle_path = output_dir / "harness_bundle.json"

    _write_json(bundle_path, harness_bundle)
    _write_json(
        output_dir / "adapter_contract.json",
        {
            "tau2_root": str(tau2_root),
            "domain": env.get("AUTOHARNESS_TAU2_DOMAIN", "airline"),
            "case_count": len(cases),
            "note": (
                "Each case is executed through a registered custom tau2 agent built "
                "from this harness bundle."
            ),
        },
    )

    split = env["AUTOHARNESS_SPLIT"]
    results = [
        _run_case(
            case=case,
            tau2_root=tau2_root,
            workspace_root=workspace_root,
            output_dir=output_dir / "tau2_runs" / _safe_name(case.case_id),
            bundle_path=bundle_path,
            repo_root=repo_root,
            env=env,
        )
        for case in cases
        if case.split == split
    ]

    duration_sec = sum(item["duration_sec"] for item in results)
    passed_count = sum(1 for item in results if item["passed"])
    mean_score = sum(item["score"] for item in results) / len(results) if results else 0.0
    _write_json(
        result_json_path,
        {
            "summary": {
                "split": split,
                "n_cases": len(results),
                "n_passed": passed_count,
                "mean_score": mean_score,
                "duration_sec": duration_sec,
            },
            "cases": results,
        },
    )
    return 0


def _run_case(
    *,
    case,
    tau2_root: Path,
    workspace_root: Path,
    output_dir: Path,
    bundle_path: Path,
    repo_root: Path,
    env: dict[str, str],
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    command = resolve_tau2_python_command(tau2_root, env) + [
        "-m",
        "autoharness.integrations.tau2_worker",
        "--bundle-path",
        str(bundle_path),
        "--workspace-root",
        str(workspace_root),
        "--output-dir",
        str(output_dir),
        "--domain",
        env.get("AUTOHARNESS_TAU2_DOMAIN", "airline"),
        "--case-id",
        case.case_id,
        "--split",
        case.split,
        "--task-id",
        case.task_id,
        "--task-split-name",
        env.get("AUTOHARNESS_TAU2_TASK_SPLIT_NAME", "base"),
        "--agent-model",
        _required_env(env, "AUTOHARNESS_TAU2_AGENT_MODEL"),
        "--user-model",
        _required_env(env, "AUTOHARNESS_TAU2_USER_MODEL"),
        "--user-backend",
        env.get("AUTOHARNESS_TAU2_USER_BACKEND", "user_simulator"),
        "--num-trials",
        str(case.num_trials),
        "--max-concurrency",
        env.get("AUTOHARNESS_TAU2_MAX_CONCURRENCY", "1"),
        "--seed",
        env.get("AUTOHARNESS_TAU2_SEED", "42"),
    ]
    _append_optional_flag(command, "--max-steps", env.get("AUTOHARNESS_TAU2_MAX_STEPS"))
    _append_optional_flag(command, "--max-errors", env.get("AUTOHARNESS_TAU2_MAX_ERRORS"))
    _append_optional_flag(
        command,
        "--agent-llm-args-json",
        env.get("AUTOHARNESS_TAU2_AGENT_LLM_ARGS_JSON"),
    )
    _append_optional_flag(
        command,
        "--user-llm-args-json",
        env.get("AUTOHARNESS_TAU2_USER_LLM_ARGS_JSON"),
    )
    _append_optional_flag(
        command,
        "--reflector-model",
        env.get("AUTOHARNESS_TAU2_REFLECTOR_MODEL"),
    )
    _append_optional_flag(
        command,
        "--skill-manager-model",
        env.get("AUTOHARNESS_TAU2_SKILL_MANAGER_MODEL"),
    )
    _append_optional_flag(
        command,
        "--reflector-llm-args-json",
        env.get("AUTOHARNESS_TAU2_REFLECTOR_LLM_ARGS_JSON"),
    )
    _append_optional_flag(
        command,
        "--skill-manager-llm-args-json",
        env.get("AUTOHARNESS_TAU2_SKILL_MANAGER_LLM_ARGS_JSON"),
    )

    start = time.perf_counter()
    child_env = dict(os.environ)
    child_env["PYTHONPATH"] = _prepend_path(str(repo_root), child_env.get("PYTHONPATH"))
    uv_cache_dir = Path(
        env.get(
            "AUTOHARNESS_TAU2_UV_CACHE_DIR",
            output_dir.parent / ".uv-cache",
        )
    ).resolve()
    uv_cache_dir.mkdir(parents=True, exist_ok=True)
    child_env.setdefault("UV_CACHE_DIR", str(uv_cache_dir))
    child_env.setdefault("XDG_CACHE_HOME", str(uv_cache_dir.parent))
    completed = subprocess.run(
        command,
        cwd=workspace_root,
        env=child_env,
        capture_output=True,
        text=True,
        timeout=case.timeout_sec,
    )
    duration_sec = time.perf_counter() - start

    (output_dir / "stdout.txt").write_text(completed.stdout, encoding="utf-8")
    (output_dir / "stderr.txt").write_text(completed.stderr, encoding="utf-8")
    _write_json(
        output_dir / "command.json",
        {"command": command, "cwd": str(workspace_root), "tau2_root": str(tau2_root)},
    )

    metadata = {
        "task_id": case.task_id,
        "tau2_root": str(tau2_root),
        "returncode": completed.returncode,
        "stdout_path": "stdout.txt",
        "stderr_path": "stderr.txt",
        "command_path": "command.json",
        "bundle_path": str(bundle_path),
    }

    worker_result_path = output_dir / "worker_result.json"
    if worker_result_path.exists():
        worker_result = _load_json(worker_result_path)
        metadata["worker_result_path"] = "worker_result.json"
        if worker_result.get("results_path"):
            metadata["tau2_results_path"] = str(worker_result["results_path"])
    else:
        worker_result = None

    if completed.returncode != 0:
        return {
            "case_id": case.case_id,
            "split": case.split,
            "passed": False,
            "score": 0.0,
            "duration_sec": duration_sec,
            "metadata": metadata | {"error": f"tau2 exited with {completed.returncode}"},
        }

    if worker_result is None:
        return {
            "case_id": case.case_id,
            "split": case.split,
            "passed": False,
            "score": 0.0,
            "duration_sec": duration_sec,
            "metadata": metadata | {"error": "missing_worker_result"},
        }

    return {
        "case_id": case.case_id,
        "split": case.split,
        "passed": bool(worker_result["passed"]),
        "score": float(worker_result["score"]),
        "duration_sec": duration_sec,
        "metadata": metadata | {k: v for k, v in worker_result.items() if k not in {"passed", "score"}},
    }


def _load_harness_bundle(workspace_root: Path) -> dict[str, object]:
    module_path = workspace_root / "agent.py"
    spec = importlib.util.spec_from_file_location("autoharness_tau2_agent", module_path)
    if spec is None or spec.loader is None:
        return {"error": f"Could not load harness module at {module_path}"}
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("autoharness_tau2_agent", module)
    sys.path.insert(0, str(workspace_root))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)

    if hasattr(module, "build_harness_bundle"):
        return dict(module.build_harness_bundle())
    if hasattr(module, "build_agent"):
        return {"agent": module.build_agent()}
    return {"warning": "agent.py does not expose build_harness_bundle() or build_agent()."}


def _required_env(env: dict[str, str], key: str) -> str:
    value = env.get(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _append_optional_flag(command: list[str], flag: str, value: str | None) -> None:
    if value not in (None, ""):
        command.extend([flag, value])


def _prepend_path(path: str, existing: str | None) -> str:
    if not existing:
        return path
    return f"{path}{os.pathsep}{existing}"


def _safe_name(value: str) -> str:
    safe = []
    for char in value:
        safe.append(char if char.isalnum() or char in ("-", "_", ".") else "_")
    return "".join(safe)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
