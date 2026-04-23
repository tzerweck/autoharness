from __future__ import annotations

import json
import sys
import types
from pathlib import Path

from autoharness.integrations.tau2 import (
    build_tau2_run_command,
    load_autoharness_case_manifest,
    resolve_tau2_root,
    resolve_tau2_python_command,
    summarize_tau2_case,
)
from autoharness.integrations.tau2_worker import _install_tau2_import_shims, _message_text


def test_resolve_tau2_root_prefers_explicit_env(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    tau2_root = tmp_path / "tau2-bench"
    tau2_root.mkdir()
    (tau2_root / "pyproject.toml").write_text("[project]\nname='tau2'\n", encoding="utf-8")
    (tau2_root / "docs").mkdir()

    resolved = resolve_tau2_root(
        workspace,
        {"AUTOHARNESS_TAU2_ROOT": str(tau2_root)},
    )

    assert resolved == tau2_root.resolve()


def test_resolve_tau2_root_finds_repo_sibling_checkout(tmp_path: Path) -> None:
    repo_root = tmp_path / "autoharnessengineering"
    workspace = repo_root / "examples" / "tau2_airline_agent"
    workspace.mkdir(parents=True)
    tau2_root = tmp_path / "tau2-bench"
    tau2_root.mkdir()
    (tau2_root / "pyproject.toml").write_text("[project]\nname='tau2'\n", encoding="utf-8")
    (tau2_root / "docs").mkdir()

    resolved = resolve_tau2_root(workspace)

    assert resolved == tau2_root.resolve()


def test_load_autoharness_case_manifest_extracts_task_ids(tmp_path: Path) -> None:
    manifest_path = tmp_path / "cases_manifest.json"
    manifest_path.write_text(
        json.dumps(
            [
                {
                    "id": "train.airline_0001",
                    "split": "train",
                    "runner_ref": "tau2.airline.task.1",
                    "timeout_sec": 30.0,
                    "metadata": {"task_id": "1", "num_trials": 2},
                }
            ]
        ),
        encoding="utf-8",
    )

    cases = load_autoharness_case_manifest(manifest_path)

    assert len(cases) == 1
    assert cases[0].task_id == "1"
    assert cases[0].num_trials == 2
    assert cases[0].timeout_sec == 30.0


def test_resolve_tau2_python_command_prefers_explicit_python(tmp_path: Path) -> None:
    tau2_root = tmp_path / "tau2-bench"
    tau2_root.mkdir()
    python_path = tmp_path / "python"
    python_path.write_text("", encoding="utf-8")

    command = resolve_tau2_python_command(
        tau2_root,
        {"AUTOHARNESS_TAU2_PYTHON": str(python_path)},
    )

    assert command == [str(python_path.resolve())]


def test_resolve_tau2_python_command_falls_back_to_uv(tmp_path: Path) -> None:
    tau2_root = tmp_path / "tau2-bench"
    tau2_root.mkdir()

    command = resolve_tau2_python_command(tau2_root)

    assert command == [
        "uv",
        "run",
        "--directory",
        str(tau2_root.resolve()),
        "--extra",
        "knowledge",
        "--with",
        "scipy",
        "--with",
        "websockets",
        "python",
    ]


def test_tau2_worker_installs_pyaudio_stub(monkeypatch) -> None:
    monkeypatch.delitem(sys.modules, "websockets", raising=False)
    monkeypatch.delitem(sys.modules, "scipy", raising=False)
    monkeypatch.delitem(sys.modules, "scipy.signal", raising=False)
    monkeypatch.delitem(sys.modules, "audioop", raising=False)
    monkeypatch.delitem(sys.modules, "pyaudio", raising=False)
    monkeypatch.delitem(sys.modules, "elevenlabs", raising=False)

    _install_tau2_import_shims()

    websockets = sys.modules["websockets"]
    scipy = sys.modules["scipy"]
    scipy_signal = sys.modules["scipy.signal"]
    audioop = sys.modules["audioop"]
    pyaudio = sys.modules["pyaudio"]
    elevenlabs = sys.modules["elevenlabs"]
    assert hasattr(websockets, "connect")
    assert hasattr(scipy, "signal")
    assert hasattr(scipy_signal, "butter")
    assert hasattr(audioop, "ratecv")
    assert hasattr(pyaudio, "PyAudio")
    assert hasattr(pyaudio, "paInt16")
    assert hasattr(elevenlabs, "ElevenLabs")


def test_tau2_worker_message_text_handles_multitool_messages(monkeypatch) -> None:
    tau2_module = types.ModuleType("tau2")
    data_model_module = types.ModuleType("tau2.data_model")
    message_module = types.ModuleType("tau2.data_model.message")

    class FakeToolMessage:
        def __init__(self, content: str) -> None:
            self.content = content

    class FakeMultiToolMessage:
        def __init__(self, tool_messages: list[FakeToolMessage]) -> None:
            self.tool_messages = tool_messages

    message_module.MultiToolMessage = FakeMultiToolMessage
    monkeypatch.setitem(sys.modules, "tau2", tau2_module)
    monkeypatch.setitem(sys.modules, "tau2.data_model", data_model_module)
    monkeypatch.setitem(sys.modules, "tau2.data_model.message", message_module)

    message = FakeMultiToolMessage([FakeToolMessage("alpha"), FakeToolMessage("beta")])

    assert _message_text(message) == "alpha\nbeta"


def test_build_tau2_run_command_includes_fixed_task_ids_and_args() -> None:
    command = build_tau2_run_command(
        domain="airline",
        agent_model="bedrock/agent",
        user_model="bedrock/user",
        task_ids=["7", "8"],
        save_to="my-run",
        num_trials=2,
        task_split_name="base",
        max_concurrency=1,
        agent_backend="custom_agent",
        user_backend="user_simulator",
        max_steps=120,
        max_errors=4,
        agent_llm_args={"temperature": 0.0},
        user_llm_args={"temperature": 0.1},
    )

    assert command[:4] == ["uv", "run", "tau2", "run"]
    assert "--task-ids" in command
    assert "--user-llm-args" in command
    assert '{"temperature": 0.1}' in command
    assert "7" in command and "8" in command
    assert "--agent" in command and "custom_agent" in command
    assert "--save-to" in command and "my-run" in command


def test_summarize_tau2_case_prefers_matching_task_record(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps(
            {
                "simulations": [
                    {"task_id": 1, "reward": 0.0},
                    {"task_id": 2, "metrics": {"pass_1": 100.0}},
                ]
            }
        ),
        encoding="utf-8",
    )

    passed, score, metadata = summarize_tau2_case(results_path, "2")

    assert passed is True
    assert score == 1.0
    assert metadata["parse_mode"] == "task_record"
    assert metadata["score_source"] == "metrics.pass_1"
