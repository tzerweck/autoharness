"""Helpers for wiring AutoHarness to tau2-bench text evaluations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from autoharness.errors import AutoharnessError

TAU2_ROOT_ENV = "AUTOHARNESS_TAU2_ROOT"
TAU2_PYTHON_ENV = "AUTOHARNESS_TAU2_PYTHON"


@dataclass(frozen=True)
class Tau2CaseSpec:
    case_id: str
    split: str
    task_id: str
    runner_ref: str
    timeout_sec: float | None
    num_trials: int
    metadata: dict[str, Any]


def resolve_tau2_root(
    workspace_root: Path,
    environ: Mapping[str, str] | None = None,
) -> Path:
    env = environ or {}
    candidates: list[Path] = []
    explicit = env.get(TAU2_ROOT_ENV)
    if explicit:
        candidates.append(Path(explicit).expanduser().resolve())

    workspace_root = workspace_root.resolve()
    candidates.extend(
        [
            workspace_root / "external" / "tau2-bench",
            workspace_root.parent / "tau2-bench",
            workspace_root.parent / "external" / "tau2-bench",
            workspace_root.parents[1] / "tau2-bench",
            workspace_root.parents[1] / "external" / "tau2-bench",
            workspace_root.parents[2] / "tau2-bench",
            workspace_root.parents[2] / "external" / "tau2-bench",
        ]
    )

    for candidate in candidates:
        if _looks_like_tau2_root(candidate):
            return candidate

    searched = ", ".join(str(path) for path in candidates)
    raise AutoharnessError(
        "Could not find a tau2-bench checkout. Set "
        f"{TAU2_ROOT_ENV} or clone tau2-bench into one of: {searched}"
    )


def load_autoharness_case_manifest(path: Path) -> list[Tau2CaseSpec]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise AutoharnessError(f"Expected a JSON list in case manifest: {path}")

    cases: list[Tau2CaseSpec] = []
    for index, raw_case in enumerate(payload):
        if not isinstance(raw_case, dict):
            raise AutoharnessError(f"Invalid case at index {index} in {path}")
        metadata = dict(raw_case.get("metadata", {}))
        task_id = metadata.get("task_id", raw_case.get("runner_ref"))
        if task_id in (None, ""):
            raise AutoharnessError(
                f"Case '{raw_case.get('id', index)}' is missing metadata.task_id."
            )
        num_trials = int(metadata.get("num_trials", 1))
        cases.append(
            Tau2CaseSpec(
                case_id=str(raw_case["id"]),
                split=str(raw_case["split"]),
                task_id=str(task_id),
                runner_ref=str(raw_case.get("runner_ref", task_id)),
                timeout_sec=_coerce_optional_float(raw_case.get("timeout_sec")),
                num_trials=num_trials,
                metadata=metadata,
            )
        )
    return cases


def resolve_tau2_python_command(
    tau2_root: Path,
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    env = environ or {}
    explicit = env.get(TAU2_PYTHON_ENV)
    if explicit:
        return [str(Path(explicit).expanduser().resolve())]

    tau2_root = tau2_root.resolve()
    # tau2's current import graph reaches optional voice/audio modules that need scipy.
    # It also touches websocket-based transcription modules during import. Drive
    # tau2 through uv by default so we can inject those compatibility deps even
    # if the checkout's local virtualenv is incomplete.
    return [
        "uv",
        "run",
        "--directory",
        str(tau2_root),
        "--extra",
        "knowledge",
        "--with",
        "scipy",
        "--with",
        "websockets",
        "python",
    ]


def build_tau2_run_command(
    *,
    domain: str,
    agent_model: str,
    user_model: str,
    task_ids: list[str],
    save_to: str,
    num_trials: int = 1,
    task_split_name: str = "base",
    max_concurrency: int = 1,
    agent_backend: str = "llm_agent",
    user_backend: str = "user_simulator",
    max_steps: int | None = None,
    max_errors: int | None = None,
    agent_llm_args: dict[str, Any] | None = None,
    user_llm_args: dict[str, Any] | None = None,
) -> list[str]:
    command = [
        "uv",
        "run",
        "tau2",
        "run",
        "--domain",
        domain,
        "--agent",
        agent_backend,
        "--user",
        user_backend,
        "--agent-llm",
        agent_model,
        "--user-llm",
        user_model,
        "--num-trials",
        str(num_trials),
        "--max-concurrency",
        str(max_concurrency),
        "--task-split-name",
        task_split_name,
        "--save-to",
        save_to,
        "--task-ids",
        *task_ids,
    ]
    if max_steps is not None:
        command.extend(["--max-steps", str(max_steps)])
    if max_errors is not None:
        command.extend(["--max-errors", str(max_errors)])
    if agent_llm_args:
        command.extend(["--agent-llm-args", json.dumps(agent_llm_args, sort_keys=True)])
    if user_llm_args:
        command.extend(["--user-llm-args", json.dumps(user_llm_args, sort_keys=True)])
    return command


def summarize_tau2_case(results_path: Path, task_id: str) -> tuple[bool, float, dict[str, Any]]:
    payload = json.loads(results_path.read_text(encoding="utf-8"))
    record = _find_task_record(payload, task_id)
    if record is not None:
        score = _extract_score(record)
        return (
            score >= 1.0,
            score,
            {
                "parse_mode": "task_record",
                "task_id": task_id,
                "score_source": _score_source(record),
            },
        )

    summary = _extract_summary_score(payload)
    if summary is not None:
        return (
            summary >= 1.0,
            summary,
            {
                "parse_mode": "summary_fallback",
                "task_id": task_id,
                "score_source": "pass_1",
            },
        )

    raise AutoharnessError(
        f"Could not derive a score for tau2 task {task_id} from {results_path}."
    )


def _looks_like_tau2_root(path: Path) -> bool:
    return path.exists() and (path / "pyproject.toml").exists() and (path / "docs").exists()


def _coerce_optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _find_task_record(payload: Any, task_id: str) -> dict[str, Any] | None:
    task_id = str(task_id)
    for item in _walk_json(payload):
        if not isinstance(item, dict):
            continue
        for key in ("task_id", "taskId", "id"):
            if str(item.get(key, "")) == task_id:
                return item
    return None


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_json(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _extract_summary_score(payload: dict[str, Any]) -> float | None:
    for item in _walk_json(payload):
        if not isinstance(item, dict):
            continue
        if "pass_1" in item:
            return _normalize_score(item["pass_1"], "pass_1")
    return None


def _extract_score(payload: dict[str, Any]) -> float:
    for key in ("reward", "score", "pass_1", "pass1", "success", "passed", "completed"):
        if key in payload:
            return _normalize_score(payload[key], key)
    for nested_key in ("metrics", "summary", "result", "evaluation"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            try:
                return _extract_score(nested)
            except AutoharnessError:
                continue
    raise AutoharnessError(f"Could not extract a score from tau2 task record: {payload}")


def _score_source(payload: dict[str, Any]) -> str:
    for key in ("reward", "score", "pass_1", "pass1", "success", "passed", "completed"):
        if key in payload:
            return key
    for nested_key in ("metrics", "summary", "result", "evaluation"):
        nested = payload.get(nested_key)
        if isinstance(nested, dict):
            try:
                nested_source = _score_source(nested)
                return f"{nested_key}.{nested_source}"
            except AutoharnessError:
                continue
    raise AutoharnessError(f"Could not identify a score source in tau2 task record: {payload}")


def _normalize_score(value: Any, key: str) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    score = float(value)
    if key.startswith("pass") and score > 1.0:
        return score / 100.0
    return score
