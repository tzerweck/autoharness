"""Programmatic tau2 worker executed inside a tau2-compatible Python environment."""

from __future__ import annotations

import argparse
import json
import importlib
import sys
import types
import uuid
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        harness_bundle = _load_json(Path(args.bundle_path))
        result = _run_tau2_case(args, harness_bundle, output_dir)
        _write_json(output_dir / "worker_result.json", result)
        return 0
    except Exception as exc:
        _write_json(
            output_dir / "worker_error.json",
            {
                "error": str(exc),
                "error_type": type(exc).__name__,
                "task_id": args.task_id,
            },
        )
        raise


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-path", required=True)
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--domain", default="airline")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--split", required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-split-name", default="base")
    parser.add_argument("--agent-model", required=True)
    parser.add_argument("--user-model", required=True)
    parser.add_argument("--reflector-model")
    parser.add_argument("--skill-manager-model")
    parser.add_argument("--user-backend", default="user_simulator")
    parser.add_argument("--num-trials", type=int, default=1)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--max-errors", type=int)
    parser.add_argument("--agent-llm-args-json")
    parser.add_argument("--user-llm-args-json")
    parser.add_argument("--reflector-llm-args-json")
    parser.add_argument("--skill-manager-llm-args-json")
    return parser.parse_args(argv)


def _run_tau2_case(
    args: argparse.Namespace,
    harness_bundle: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    _install_tau2_import_shims()
    workspace_root = Path(args.workspace_root).resolve()
    sys.path.insert(0, str(workspace_root))

    from tau2.agent.base_agent import HalfDuplexAgent, ValidAgentInputMessage
    from tau2.data_model.message import (
        APICompatibleMessage,
        AssistantMessage,
        Message,
        MultiToolMessage,
        SystemMessage,
    )
    from tau2.data_model.simulation import TextRunConfig
    from tau2.registry import registry
    from tau2.runner import get_tasks, run_tasks
    from tau2.utils.llm_utils import generate
    ace_runtime = importlib.import_module("ace.runtime")

    agent_llm_args = _optional_json_dict(args.agent_llm_args_json)
    user_llm_args = _optional_json_dict(args.user_llm_args_json)
    reflector_llm_args = _optional_json_dict(args.reflector_llm_args_json)
    skill_manager_llm_args = _optional_json_dict(args.skill_manager_llm_args_json)
    episode_artifacts: dict[str, Any] = {}

    class AutoHarnessAgentState:
        def __init__(
            self,
            system_messages: list[SystemMessage],
            messages: list[APICompatibleMessage],
            episode_context: dict[str, Any] | None = None,
        ) -> None:
            self.system_messages = system_messages
            self.messages = messages
            self.episode_context = episode_context

    class AutoHarnessTau2Agent(HalfDuplexAgent[AutoHarnessAgentState]):
        def __init__(
            self,
            tools,
            domain_policy: str,
            llm: str,
            llm_args: dict[str, Any] | None,
        ) -> None:
            super().__init__(tools=tools, domain_policy=domain_policy)
            self.llm = llm
            self.llm_args = llm_args or {}
            self._base_system_prompt = ace_runtime.build_system_prompt(
                harness_bundle=harness_bundle,
                domain_policy=domain_policy,
                tools=tools,
            )

        def get_init_state(
            self,
            message_history: list[Message] | None = None,
        ) -> AutoHarnessAgentState:
            return AutoHarnessAgentState(
                system_messages=[
                    SystemMessage(role="system", content=self._base_system_prompt)
                ],
                messages=list(message_history) if message_history else [],
            )

        def generate_next_message(
            self,
            message: ValidAgentInputMessage,
            state: AutoHarnessAgentState,
        ) -> tuple[AssistantMessage, AutoHarnessAgentState]:
            if state.episode_context is None:
                episode_context = ace_runtime.prepare_episode_context(
                    harness_bundle=harness_bundle,
                    case_output_dir=output_dir,
                    split=args.split,
                    case_id=args.case_id,
                    first_user_message_text=_message_text(message),
                )
                state.system_messages = [
                    SystemMessage(
                        role="system",
                        content=ace_runtime.build_system_prompt(
                            harness_bundle=harness_bundle,
                            domain_policy=self.domain_policy,
                            tools=self.tools,
                            skill_block=str(episode_context.get("skill_block", "")),
                        ),
                    )
                ]
                state.episode_context = episode_context
                episode_artifacts["episode_context"] = episode_context
            if isinstance(message, MultiToolMessage):
                state.messages.extend(message.tool_messages)
            else:
                state.messages.append(message)

            assistant_message = generate(
                model=self.llm,
                tools=self.tools,
                messages=state.system_messages + state.messages,
                call_name="autoharness_tau2_agent",
                **self.llm_args,
            )
            state.messages.append(assistant_message)
            return assistant_message, state

    def create_agent(tools, domain_policy, **kwargs):
        return AutoHarnessTau2Agent(
            tools=tools,
            domain_policy=domain_policy,
            llm=kwargs.get("llm", args.agent_model),
            llm_args=kwargs.get("llm_args", agent_llm_args),
        )

    agent_name = f"autoharness_tau2_agent_{uuid.uuid4().hex[:8]}"
    registry.register_agent_factory(create_agent, agent_name)
    tasks = get_tasks(
        args.domain,
        task_split_name=args.task_split_name,
        task_ids=[args.task_id],
    )

    config_kwargs: dict[str, Any] = {
        "domain": args.domain,
        "agent": agent_name,
        "user": args.user_backend,
        "llm_agent": args.agent_model,
        "llm_args_agent": agent_llm_args or {},
        "llm_user": args.user_model,
        "llm_args_user": user_llm_args or {},
        "num_trials": args.num_trials,
        "max_concurrency": args.max_concurrency,
        "seed": args.seed,
    }
    if args.max_steps is not None:
        config_kwargs["max_steps"] = args.max_steps
    if args.max_errors is not None:
        config_kwargs["max_errors"] = args.max_errors

    results = run_tasks(
        TextRunConfig(**config_kwargs),
        tasks,
        save_path=output_dir / "results.json",
        save_dir=output_dir,
        console_display=False,
    )

    simulations = [sim for sim in results.simulations if sim.task_id == args.task_id]
    rewards = [
        float(sim.reward_info.reward) if sim.reward_info is not None else 0.0
        for sim in simulations
    ]
    mean_reward = sum(rewards) / len(rewards) if rewards else 0.0
    passed = mean_reward >= 1.0
    learning_artifact = ace_runtime.maybe_update_skill_store(
        harness_bundle=harness_bundle,
        case_output_dir=output_dir,
        split=args.split,
        case_id=args.case_id,
        simulations=simulations,
        mean_reward=mean_reward,
        reflector_model=args.reflector_model or args.agent_model,
        skill_manager_model=args.skill_manager_model or args.agent_model,
        reflector_llm_args=reflector_llm_args,
        skill_manager_llm_args=skill_manager_llm_args,
        call_text_model=_call_text_model,
    )

    result = {
        "case_id": args.case_id,
        "task_id": args.task_id,
        "passed": passed,
        "score": mean_reward,
        "aggregate": "mean_reward",
        "num_trials": len(simulations),
        "trial_rewards": rewards,
        "agent_cost": sum(sim.agent_cost or 0.0 for sim in simulations),
        "user_cost": sum(sim.user_cost or 0.0 for sim in simulations),
        "sim_duration_sec": sum(sim.duration or 0.0 for sim in simulations),
        "results_path": "results.json",
        "agent_name": agent_name,
        "runtime_mode": str(learning_artifact.get("mode", "")),
        "retrieved_skill_count": len(
            (episode_artifacts.get("episode_context") or {}).get("retrieved_skills", [])
        ),
        "store_after_count": learning_artifact.get("store_after_count"),
    }
    _write_json(output_dir / "bundle_used.json", harness_bundle)
    if episode_artifacts:
        _write_json(output_dir / "ace" / "episode_context.json", episode_artifacts["episode_context"])
    _write_json(output_dir / "ace" / "learning.json", learning_artifact)
    return result


def _install_tau2_import_shims() -> None:
    """Stub optional audio-only imports that tau2 reaches during text-mode startup."""
    if "websockets" not in sys.modules:
        module = types.ModuleType("websockets")

        def _unsupported_websocket(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("websockets stub should not be used for text-mode tau2 runs.")

        module.connect = _unsupported_websocket
        sys.modules["websockets"] = module

    if "scipy" not in sys.modules:
        scipy_module = types.ModuleType("scipy")
        signal_module = types.ModuleType("scipy.signal")

        def _unsupported_signal(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("scipy.signal stub should not be used for text-mode tau2 runs.")

        signal_module.butter = _unsupported_signal
        signal_module.lfilter = _unsupported_signal
        signal_module.filtfilt = _unsupported_signal
        signal_module.resample_poly = _unsupported_signal
        scipy_module.signal = signal_module
        sys.modules["scipy"] = scipy_module
        sys.modules["scipy.signal"] = signal_module

    if "audioop" not in sys.modules:
        module = types.ModuleType("audioop")

        def _unsupported(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("audioop stub should not be used for text-mode tau2 runs.")

        module.ratecv = _unsupported
        module.ulaw2lin = _unsupported
        module.lin2ulaw = _unsupported
        module.bias = _unsupported
        module.lin2lin = _unsupported
        module.alaw2lin = _unsupported
        module.lin2alaw = _unsupported
        module.tomono = _unsupported
        sys.modules["audioop"] = module

    if "pyaudio" not in sys.modules:
        module = types.ModuleType("pyaudio")

        class _StubPyAudio:
            def open(self, *args: Any, **kwargs: Any) -> Any:
                raise RuntimeError("pyaudio stub should not be used for text-mode tau2 runs.")

            def terminate(self) -> None:
                return None

        module.PyAudio = _StubPyAudio
        module.paInt8 = 0
        module.paInt16 = 0
        module.paInt32 = 0
        sys.modules["pyaudio"] = module

    if "elevenlabs" not in sys.modules:
        module = types.ModuleType("elevenlabs")

        class _StubElevenLabs:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                raise RuntimeError(
                    "elevenlabs stub should not be used for text-mode tau2 runs."
                )

        module.ElevenLabs = _StubElevenLabs
        sys.modules["elevenlabs"] = module


def _call_text_model(
    model: str,
    system_prompt: str,
    user_prompt: str,
    llm_args: dict[str, Any] | None,
    call_name: str,
) -> str:
    from tau2.data_model.message import SystemMessage, UserMessage
    from tau2.utils.llm_utils import generate

    response = generate(
        model=model,
        tools=[],
        messages=[
            SystemMessage(role="system", content=system_prompt),
            UserMessage(role="user", content=user_prompt),
        ],
        call_name=call_name,
        **(llm_args or {}),
    )
    return str(response.content or "")


def _message_text(message: Any) -> str:
    multi_tool_message_type = _load_multi_tool_message_type()
    if multi_tool_message_type is not None and isinstance(message, multi_tool_message_type):
        parts = [_message_text(item) for item in message.tool_messages]
        return "\n".join(part for part in parts if part).strip()
    content = getattr(message, "content", None)
    if content:
        return str(content)
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        return ", ".join(str(getattr(call, "name", "tool")) for call in tool_calls)
    return ""


def _load_multi_tool_message_type() -> type[Any] | None:
    try:
        from tau2.data_model.message import MultiToolMessage
    except Exception:
        return None
    return MultiToolMessage


def _optional_json_dict(value: str | None) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object.")
    return payload


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object at {path}.")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
