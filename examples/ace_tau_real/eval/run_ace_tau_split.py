"""AutoHarness runner for the clean ACE snapshot on fixed tau2 tasks."""

from __future__ import annotations

import json
import os
import sys
import types
import uuid
from pathlib import Path
from typing import Any

from autoharness.integrations.tau2 import load_autoharness_case_manifest, resolve_tau2_root


def main() -> int:
    env = os.environ
    workspace_root = Path(env["AUTOHARNESS_WORKSPACE_ROOT"]).resolve()
    output_dir = Path(env["AUTOHARNESS_OUTPUT_DIR"]).resolve()
    manifest_path = Path(env["AUTOHARNESS_CASES_MANIFEST"]).resolve()
    result_json_path = Path(env["AUTOHARNESS_RESULT_JSON_PATH"]).resolve()
    split = env["AUTOHARNESS_SPLIT"]

    tau2_root = resolve_tau2_root(workspace_root, env)
    _configure_tau2_data_dir(tau2_root)
    _install_tau2_import_shims()

    cases = [case for case in load_autoharness_case_manifest(manifest_path) if case.split == split]
    output_dir.mkdir(parents=True, exist_ok=True)

    from ace import Skillbook

    state_root = output_dir.parent / "ace_state"
    skillbook = _load_skillbook_for_split(state_root, split, Skillbook)
    mode = env.get("AUTOHARNESS_ACE_MODE", "ace_static").strip() or "ace_static"
    roles = _build_roles(env, mode=mode)

    case_results: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        case_output_dir = output_dir / _safe_name(case.case_id)
        case_result = _run_case(
            workspace_root=workspace_root,
            tau2_root=tau2_root,
            output_dir=case_output_dir,
            split=split,
            case=case,
            skillbook=skillbook,
            mode=mode,
            roles=roles,
            progress=f"{split} {index + 1}/{len(cases)}",
            env=env,
        )
        case_results.append(case_result)
        if split == "train":
            _persist_train_skillbook(state_root, skillbook)

    summary = {
        "split": split,
        "n_cases": len(case_results),
        "n_passed": sum(1 for item in case_results if item["passed"]),
        "mean_score": (
            sum(float(item["score"]) for item in case_results) / len(case_results)
            if case_results
            else 0.0
        ),
        "duration_sec": sum(float(item["duration_sec"]) for item in case_results),
    }
    result_json_path.write_text(
        json.dumps({"summary": summary, "cases": case_results}, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )
    return 0


def _build_roles(env: dict[str, str], *, mode: str) -> dict[str, Any] | None:
    if mode == "plain":
        return None
    from ace.implementations import SkillManager

    reflector_model = _required_env(env, "AUTOHARNESS_ACE_REFLECTOR_MODEL")
    skill_manager_model = _required_env(env, "AUTOHARNESS_ACE_SKILL_MANAGER_MODEL")
    reflector_settings = _optional_model_settings(env.get("AUTOHARNESS_ACE_REFLECTOR_LLM_ARGS_JSON"))
    skill_manager_settings = _optional_model_settings(
        env.get("AUTOHARNESS_ACE_SKILL_MANAGER_LLM_ARGS_JSON")
    )
    reflector_impl = env.get("AUTOHARNESS_ACE_REFLECTOR_IMPL", "simple").strip().lower() or "simple"

    if reflector_impl == "rr":
        from ace.rr import RRConfig, RRStep

        rr_config = RRConfig(
            max_iterations=int(env.get("AUTOHARNESS_ACE_RR_MAX_ITERATIONS", "20")),
            timeout=float(env.get("AUTOHARNESS_ACE_RR_TIMEOUT_SEC", "30.0")),
            max_llm_calls=int(env.get("AUTOHARNESS_ACE_RR_MAX_LLM_CALLS", "30")),
            enable_subagent=_env_flag(
                env.get("AUTOHARNESS_ACE_RR_ENABLE_SUBAGENT"),
                default=True,
            ),
            subagent_model=env.get("AUTOHARNESS_ACE_RR_SUBAGENT_MODEL", "").strip() or None,
            subagent_max_requests=int(
                env.get("AUTOHARNESS_ACE_RR_SUBAGENT_MAX_REQUESTS", "15")
            ),
        )
        reflector = RRStep(
            reflector_model,
            config=rr_config,
            model_settings=reflector_settings,
        )
    else:
        from ace.implementations import Reflector

        reflector = Reflector(
            reflector_model,
            model_settings=reflector_settings,
        )

    return {
        "reflector": reflector,
        "skill_manager": SkillManager(
            skill_manager_model,
            model_settings=skill_manager_settings,
        ),
    }


def _run_case(
    *,
    workspace_root: Path,
    tau2_root: Path,
    output_dir: Path,
    split: str,
    case,
    skillbook,
    mode: str,
    roles: dict[str, Any] | None,
    progress: str,
    env: dict[str, str],
) -> dict[str, Any]:
    from ace.core.outputs import AgentOutput
    from ace.implementations.helpers import extract_cited_skill_ids
    from ace.rr.trace_context import TraceContext
    from tau2.data_model.message import Message
    from tau2.data_model.simulation import TextRunConfig
    from tau2.registry import registry
    from tau2.runner import get_tasks, run_tasks

    output_dir.mkdir(parents=True, exist_ok=True)
    agent_model = _required_env(env, "AUTOHARNESS_ACE_AGENT_MODEL")
    user_model = _required_env(env, "AUTOHARNESS_ACE_USER_MODEL")
    agent_llm_args = _optional_json_dict(env.get("AUTOHARNESS_ACE_AGENT_LLM_ARGS_JSON")) or {}
    user_llm_args = _optional_json_dict(env.get("AUTOHARNESS_ACE_USER_LLM_ARGS_JSON")) or {}

    tasks = get_tasks(
        env.get("AUTOHARNESS_ACE_DOMAIN", "airline"),
        task_split_name=env.get("AUTOHARNESS_TAU2_TASK_SPLIT_NAME", "base"),
        task_ids=[case.task_id],
    )
    if not tasks:
        return _error_case_result(case, f"task_not_found:{case.task_id}")
    task = tasks[0]

    episode_artifacts: dict[str, Any] = {}
    task_question = _task_question(task)
    task_context = _task_context(task)

    class _AgentState:
        def __init__(self, system_messages: list[Any], messages: list[Message]) -> None:
            self.system_messages = system_messages
            self.messages = messages
            self.effective_policy = ""
            self.injected_context_chars = 0

    def create_agent(tools, domain_policy, **kwargs):
        from tau2.agent.base_agent import HalfDuplexAgent, ValidAgentInputMessage
        from tau2.agent.llm_agent import LLMAgent
        from tau2.data_model.message import MultiToolMessage, SystemMessage

        class _AceTauAgent(HalfDuplexAgent[_AgentState]):
            def __init__(self) -> None:
                super().__init__(tools=tools, domain_policy=domain_policy)
                self._agent = LLMAgent(
                    tools=tools,
                    domain_policy=domain_policy,
                    llm=kwargs.get("llm", agent_model),
                    llm_args=kwargs.get("llm_args", agent_llm_args),
                )
                self.base_domain_policy = domain_policy

            def _refresh(self, state: _AgentState, current_message: Any | None) -> None:
                rendered = ""
                render_artifact: dict[str, Any] | None = None
                if mode != "plain":
                    rendered, render_artifact = _render_skill_context(
                        skillbook=skillbook,
                        question=task_question,
                        context=task_context,
                        current_message=current_message,
                    )
                effective_policy = self.base_domain_policy
                if rendered:
                    effective_policy = f"{self.base_domain_policy}\n\n{rendered}"
                self._agent.domain_policy = effective_policy
                state.system_messages = [
                    SystemMessage(role="system", content=self._agent.system_prompt)
                ]
                state.effective_policy = effective_policy
                state.injected_context_chars = len(rendered)
                if render_artifact is not None:
                    retrievals = episode_artifacts.setdefault("retrievals", [])
                    retrievals.append(
                        {
                            **render_artifact,
                            "effective_policy_chars": len(effective_policy),
                        }
                    )

            def get_init_state(
                self,
                message_history: list[Message] | None = None,
            ) -> _AgentState:
                state = _AgentState(
                    system_messages=[],
                    messages=list(message_history) if message_history else [],
                )
                self._refresh(state, None)
                return state

            def generate_next_message(
                self,
                message: ValidAgentInputMessage,
                state: _AgentState,
            ):
                self._refresh(state, message)
                assistant_message, next_state = self._agent.generate_next_message(message, state)
                return assistant_message, next_state

        return _AceTauAgent()

    agent_name = f"autoharness_ace_tau_{uuid.uuid4().hex[:8]}"
    registry.register_agent_factory(create_agent, agent_name)

    config = TextRunConfig(
        domain=env.get("AUTOHARNESS_ACE_DOMAIN", "airline"),
        agent=agent_name,
        user="user_simulator",
        llm_agent=agent_model,
        llm_args_agent=agent_llm_args,
        llm_user=user_model,
        llm_args_user=user_llm_args,
        num_trials=case.num_trials,
        max_concurrency=int(env.get("AUTOHARNESS_TAU2_MAX_CONCURRENCY", "1")),
        seed=int(env.get("AUTOHARNESS_TAU2_SEED", "300")),
        task_split_name=env.get("AUTOHARNESS_TAU2_TASK_SPLIT_NAME", "base"),
        max_steps=int(env.get("AUTOHARNESS_TAU2_MAX_STEPS", "200")),
        max_errors=int(env.get("AUTOHARNESS_TAU2_MAX_ERRORS", "10")),
    )

    results = run_tasks(
        config,
        tasks,
        save_path=output_dir / "results.json",
        save_dir=output_dir,
        console_display=False,
    )
    simulations = [sim for sim in results.simulations if str(sim.task_id) == str(case.task_id)]
    rewards = [float(sim.reward_info.reward) if sim.reward_info is not None else 0.0 for sim in simulations]
    mean_reward = sum(rewards) / len(rewards) if rewards else 0.0

    learning_artifact: dict[str, Any] = {
        "mode": "read_only",
        "updated": False,
        "skills_before": len(skillbook.skills()),
        "skills_after": len(skillbook.skills()),
    }
    if mode != "plain" and split == "train" and simulations and roles is not None:
        simulation = simulations[0]
        feedback = _build_feedback(simulation)
        trace_context = TraceContext.from_tau_simulation(simulation.get_messages(), system_prompt="")
        assistant_text = "\n".join(
            message.content
            for message in simulation.get_messages()
            if getattr(message, "role", None) == "assistant"
            and isinstance(getattr(message, "content", None), str)
            and message.content
        )
        agent_output = AgentOutput(
            reasoning=trace_context.to_markdown(),
            final_answer=_extract_final_answer(simulation.get_messages()),
            skill_ids=extract_cited_skill_ids(assistant_text),
            trace_context=trace_context,
        )
        before_count = len(skillbook.skills())
        reflection = roles["reflector"].reflect(
            question=task_question,
            agent_output=agent_output,
            skillbook=skillbook,
            ground_truth=None,
            feedback=feedback,
        )
        skill_manager_output = roles["skill_manager"].update_skills(
            reflections=(reflection,),
            skillbook=skillbook,
            question_context=task_context,
            progress=progress,
        )
        skillbook.apply_update(skill_manager_output.update)
        learning_artifact = {
            "mode": "train_learning",
            "updated": bool(skill_manager_output.update.operations),
            "skills_before": before_count,
            "skills_after": len(skillbook.skills()),
            "key_insight": reflection.key_insight,
            "operation_count": len(skill_manager_output.update.operations),
            "feedback": feedback,
        }

    if episode_artifacts:
        retrievals = episode_artifacts.get("retrievals", [])
        retrieved_skill_ids = sorted(
            {
                skill_id
                for retrieval in retrievals
                for skill_id in retrieval.get("selected_skill_ids", [])
            }
        )
        _write_json(
            output_dir / "ace_context.json",
            {
                "mode": mode,
                "retrieval_count": len(retrievals),
                "retrieved_skill_ids": retrieved_skill_ids,
                "retrievals": retrievals,
            },
        )
        learning_artifact["retrieved_skill_ids"] = retrieved_skill_ids
        learning_artifact["retrieval_count"] = len(retrievals)

    _write_json(output_dir / "ace_learning.json", learning_artifact)
    return {
        "case_id": case.case_id,
        "split": split,
        "passed": mean_reward >= 1.0,
        "score": mean_reward,
        "duration_sec": sum(float(sim.duration or 0.0) for sim in simulations),
        "metadata": {
            "task_id": case.task_id,
            "tau2_root": str(tau2_root),
            "results_path": str((output_dir / "results.json").relative_to(output_dir)),
            "num_trials": len(simulations),
            "trial_rewards": rewards,
            "skill_count_after": len(skillbook.skills()),
            "learning_path": "ace_learning.json",
            "retrieval_path": "ace_context.json" if episode_artifacts else None,
            "retrieved_skill_count": len(
                learning_artifact.get("retrieved_skill_ids", [])
            ),
        },
    }


def _render_skill_context(
    *,
    skillbook,
    question: str,
    context: str | None,
    current_message: Any | None,
) -> tuple[str, dict[str, Any] | None]:
    from ace import Skillbook
    from ace.implementations.prompts import wrap_skillbook_for_external_agent
    from ace.implementations.skill_rendering import retrieve_top_k

    skills = skillbook.skills()
    if not skills:
        return "", None

    query_parts = [question]
    if context:
        query_parts.append(context)
    current_text = _message_text(current_message)
    if current_text:
        query_parts.append(current_text)
    query = "\n".join(part for part in query_parts if part).strip()
    selected = retrieve_top_k(skillbook, query, top_k=min(5, len(skills)))
    if not selected:
        return "", {"query": query, "current_message": current_text, "selected_skills": []}

    subset = Skillbook()
    for skill in selected:
        subset.add_skill(
            section=skill.section,
            content=skill.content,
            skill_id=skill.id,
            justification=skill.justification,
            evidence=skill.evidence,
            insight_source=skill.sources,
        )
    rendered = wrap_skillbook_for_external_agent(subset)
    return rendered, {
        "query": query,
        "current_message": current_text,
        "rendered_chars": len(rendered),
        "selected_skill_ids": [skill.id for skill in selected],
        "selected_skills": [
            {
                "id": skill.id,
                "section": skill.section,
                "content": skill.content,
            }
            for skill in selected
        ],
    }


def _load_skillbook_for_split(state_root: Path, split: str, skillbook_cls):
    if split == "train":
        live_path = state_root / "train_live_skillbook.json"
        if live_path.exists():
            return skillbook_cls.load_from_file(str(live_path))
        return skillbook_cls()

    snapshot_path = state_root / "train_snapshot_skillbook.json"
    if snapshot_path.exists():
        return skillbook_cls.load_from_file(str(snapshot_path))
    return skillbook_cls()


def _persist_train_skillbook(state_root: Path, skillbook) -> None:
    state_root.mkdir(parents=True, exist_ok=True)
    skillbook.save_to_file(str(state_root / "train_live_skillbook.json"), exclude_embeddings=True)
    skillbook.save_to_file(str(state_root / "train_snapshot_skillbook.json"), exclude_embeddings=True)


def _configure_tau2_data_dir(tau2_root: Path) -> None:
    if os.environ.get("TAU2_DATA_DIR"):
        return
    data_dir = tau2_root / "data"
    if data_dir.exists():
        os.environ["TAU2_DATA_DIR"] = str(data_dir)


def _install_tau2_import_shims() -> None:
    if "websockets" not in sys.modules:
        module = types.ModuleType("websockets")

        def _unsupported_websocket(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("websockets stub should not be used in text mode")

        module.connect = _unsupported_websocket
        sys.modules["websockets"] = module

    if "scipy" not in sys.modules:
        scipy_module = types.ModuleType("scipy")
        signal_module = types.ModuleType("scipy.signal")

        def _unsupported_signal(*args: Any, **kwargs: Any) -> Any:
            raise RuntimeError("scipy.signal stub should not be used in text mode")

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
            raise RuntimeError("audioop stub should not be used in text mode")

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
                raise RuntimeError("pyaudio stub should not be used in text mode")

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
                raise RuntimeError("elevenlabs stub should not be used in text mode")

        module.ElevenLabs = _StubElevenLabs
        sys.modules["elevenlabs"] = module


def _task_question(task: Any) -> str:
    user_scenario = getattr(task, "user_scenario", None)
    instructions = getattr(user_scenario, "instructions", None)
    reason_for_call = getattr(instructions, "reason_for_call", None)
    if reason_for_call:
        return str(reason_for_call)
    description = getattr(task, "description", None)
    if description:
        return str(description)
    return str(instructions or user_scenario or task)


def _task_context(task: Any) -> str:
    user_scenario = getattr(task, "user_scenario", None)
    if user_scenario is not None:
        return str(user_scenario)
    return str(task)


def _extract_final_answer(messages: list[Any]) -> str:
    for message in reversed(messages):
        if getattr(message, "role", None) != "assistant":
            continue
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content
    return ""


def _build_feedback(simulation: Any) -> str:
    reward = simulation.reward_info.reward if simulation.reward_info else 0.0
    status = "SUCCEEDED" if reward >= (1.0 - 1e-6) else "FAILED"
    steps = len(simulation.get_messages())
    breakdown = simulation.reward_info.reward_breakdown if simulation.reward_info else None
    breakdown_text = ""
    if breakdown:
        rendered = ", ".join(f"{str(key)}={value:.2f}" for key, value in breakdown.items())
        breakdown_text = f", Breakdown: {rendered}"
    return (
        f"Task {status}. Reward: {reward:.2f}, Steps: {steps}, "
        f"Termination: {simulation.termination_reason}{breakdown_text}"
    )


def _message_text(message: Any | None) -> str:
    if message is None:
        return ""
    content = getattr(message, "content", None)
    if content:
        return str(content)
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        return ", ".join(str(getattr(call, "name", "tool")) for call in tool_calls)
    return ""


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value)


def _optional_json_dict(value: str | None) -> dict[str, Any] | None:
    if value in (None, ""):
        return None
    payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("Expected a JSON object.")
    return payload


def _optional_model_settings(value: str | None) -> Any | None:
    payload = _optional_json_dict(value)
    if payload is None:
        return None
    from pydantic_ai.settings import ModelSettings

    return ModelSettings(**payload)


def _env_flag(value: str | None, *, default: bool) -> bool:
    if value in (None, ""):
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Expected boolean environment flag, got: {value!r}")


def _required_env(env: dict[str, str], key: str) -> str:
    value = env.get(key)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")


def _error_case_result(case, error: str) -> dict[str, Any]:
    return {
        "case_id": case.case_id,
        "split": case.split,
        "passed": False,
        "score": 0.0,
        "duration_sec": 0.0,
        "metadata": {"task_id": case.task_id, "error": error},
    }


if __name__ == "__main__":
    raise SystemExit(main())
