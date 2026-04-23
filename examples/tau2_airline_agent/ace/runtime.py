"""ACE-static orchestration helpers for the tau2 airline example."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .reflection import propose_skills, should_reflect
from .retrieval import format_skill_block, rank_skills
from .schemas import SkillRecord, skill_from_dict, skills_to_dicts
from .skill_manager import review_skill_candidates
from .skill_store import load_skill_records, merge_skill_records, save_skill_records

BASE_AGENT_INSTRUCTIONS = """\
You are a customer service agent operating inside a benchmark harness.

In each turn you must do exactly one of the following:
- send a user-facing text response
- make one or more tool calls

Do not mix free text with tool calls in the same turn.
Use the provided tools instead of guessing.
Follow the domain policy strictly.
""".strip()


def resolve_runtime_mode(
    controller_contract: dict[str, Any],
    environ: dict[str, str] | None = None,
) -> str:
    env = environ or os.environ
    override = env.get("AUTOHARNESS_TAU2_MODE_OVERRIDE", "").strip()
    if override in {"plain", "ace_static"}:
        return override
    mode = str(controller_contract.get("mode", "ace_static")).strip()
    return mode if mode in {"plain", "ace_static"} else "ace_static"


def build_system_prompt(
    *,
    harness_bundle: dict[str, Any],
    domain_policy: str,
    tools: list[Any],
    skill_block: str = "",
) -> str:
    controller = _controller_contract(harness_bundle)
    sections = [
        _section("Base Instructions", BASE_AGENT_INSTRUCTIONS),
        _section("Harness Prompt", _text_value(harness_bundle.get("system_prompt"))),
        _section("Policy Guidance", _text_value(harness_bundle.get("policy_prompt"))),
        _section("Domain Policy", domain_policy),
        _section("Retrieved Skills", skill_block),
        _section("Tool Guidance", _text_value(harness_bundle.get("tool_instructions"))),
        _section("Agent Rules", _render_agent_rules(controller.get("agent_rules"))),
        _section("Tool Catalog", _render_tool_catalog(tools)),
    ]
    return "\n\n".join(section for section in sections if section)


def prepare_episode_context(
    *,
    harness_bundle: dict[str, Any],
    case_output_dir: Path,
    split: str,
    case_id: str,
    first_user_message_text: str,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    controller = _controller_contract(harness_bundle)
    mode = resolve_runtime_mode(controller, environ)
    settings = _mode_settings(controller)
    store_before = _load_store_for_split(case_output_dir, split, mode)
    if mode != "ace_static":
        return {
            "case_id": case_id,
            "mode": mode,
            "skill_block": "",
            "retrieved_skills": [],
            "store_before_count": len(store_before),
            "store_before": skills_to_dicts(store_before),
        }

    ranked = [
        (score, skill)
        for score, skill in rank_skills(store_before, first_user_message_text)
        if score >= int(settings.get("retrieval_min_overlap", 1))
    ]
    top_k = int(settings.get("top_k", 3))
    retrieved = [skill for _, skill in ranked[:top_k]]
    skill_block = format_skill_block(
        _text_value(harness_bundle.get("skillbook_template")),
        retrieved,
        max_chars=int(settings.get("max_skill_block_chars", 1600)),
    )
    return {
        "case_id": case_id,
        "mode": mode,
        "query_text": first_user_message_text.strip(),
        "skill_block": skill_block,
        "retrieved_skills": [
            {"score": score, **_skill_to_artifact(skill)} for score, skill in ranked[:top_k]
        ],
        "store_before_count": len(store_before),
        "store_before": skills_to_dicts(store_before),
        "state_root": str(_state_root(case_output_dir)),
    }


def maybe_update_skill_store(
    *,
    harness_bundle: dict[str, Any],
    case_output_dir: Path,
    split: str,
    case_id: str,
    simulations: list[Any],
    mean_reward: float,
    reflector_model: str,
    skill_manager_model: str,
    reflector_llm_args: dict[str, Any] | None,
    skill_manager_llm_args: dict[str, Any] | None,
    call_text_model,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    controller = _controller_contract(harness_bundle)
    mode = resolve_runtime_mode(controller, environ)
    settings = _mode_settings(controller)
    store_before = _load_store_for_train(case_output_dir)

    result: dict[str, Any] = {
        "case_id": case_id,
        "mode": mode,
        "updated": False,
        "store_before_count": len(store_before),
        "store_before": skills_to_dicts(store_before),
    }

    if mode != "ace_static" or split != "train":
        return result

    _persist_train_snapshot(case_output_dir, store_before)

    if not should_reflect(settings, mean_reward):
        result["skipped_reason"] = "reflection_disabled_for_reward_band"
        result["store_after_count"] = len(store_before)
        result["store_after"] = skills_to_dicts(store_before)
        return result

    reflection_artifact = propose_skills(
        case_id=case_id,
        simulations=simulations,
        mean_reward=mean_reward,
        reflector_prompt=_text_value(harness_bundle.get("reflector_prompt")),
        model=reflector_model,
        llm_args=reflector_llm_args,
        max_skills=int(settings.get("max_reflector_skills", 2)),
        call_text_model=call_text_model,
    )
    proposed_skills = [
        skill_from_dict(item) for item in reflection_artifact.get("proposed_skills", [])
    ]
    manager_artifact = review_skill_candidates(
        existing_skills=store_before,
        proposed_skills=proposed_skills,
        skill_manager_prompt=_text_value(harness_bundle.get("skill_manager_prompt")),
        model=skill_manager_model,
        llm_args=skill_manager_llm_args,
        max_accept=int(settings.get("max_manager_accepted_skills", 2)),
        max_store_context_skills=int(settings.get("max_store_context_skills", 12)),
        call_text_model=call_text_model,
    )
    accepted_skills = [
        SkillRecord(
            skill_id=item.skill_id,
            title=item.title,
            when_to_apply=item.when_to_apply,
            guidance=item.guidance,
            caution=item.caution,
            evidence_case_ids=[case_id],
            source=item.source,
        )
        for item in [skill_from_dict(item) for item in manager_artifact.get("accepted_skills", [])]
    ]
    merged_store = merge_skill_records(
        store_before,
        accepted_skills,
        max_store_size=int(settings.get("max_store_size", 48)),
    )
    _persist_train_snapshot(case_output_dir, merged_store)
    result.update(
        {
            "updated": bool(accepted_skills),
            "reflection": reflection_artifact,
            "skill_manager": manager_artifact,
            "store_after_count": len(merged_store),
            "store_after": skills_to_dicts(merged_store),
        }
    )
    return result


def _controller_contract(harness_bundle: dict[str, Any]) -> dict[str, Any]:
    value = harness_bundle.get("controller_contract")
    return value if isinstance(value, dict) else {}


def _mode_settings(controller_contract: dict[str, Any]) -> dict[str, Any]:
    value = controller_contract.get("ace_static")
    return value if isinstance(value, dict) else {}


def _load_store_for_split(case_output_dir: Path, split: str, mode: str) -> list[SkillRecord]:
    if mode != "ace_static":
        return []
    if split == "train":
        return _load_store_for_train(case_output_dir)
    return load_skill_records(_state_root(case_output_dir) / "train_snapshot.json")


def _load_store_for_train(case_output_dir: Path) -> list[SkillRecord]:
    return load_skill_records(_state_root(case_output_dir) / "train_live.json")


def _persist_train_snapshot(case_output_dir: Path, skills: list[SkillRecord]) -> None:
    state_root = _state_root(case_output_dir)
    save_skill_records(state_root / "train_live.json", skills)
    save_skill_records(state_root / "train_snapshot.json", skills)


def _state_root(case_output_dir: Path) -> Path:
    return case_output_dir.parents[2] / "ace_state"


def _skill_to_artifact(skill: SkillRecord) -> dict[str, Any]:
    return {
        "skill_id": skill.skill_id,
        "title": skill.title,
        "when_to_apply": skill.when_to_apply,
        "guidance": skill.guidance,
        "caution": skill.caution,
        "evidence_case_ids": list(skill.evidence_case_ids),
        "source": skill.source,
    }


def _render_tool_catalog(tools: list[Any]) -> str:
    rendered = []
    for tool in tools:
        try:
            rendered.append(str(tool))
        except Exception:
            rendered.append(getattr(tool, "name", repr(tool)))
    return "\n\n".join(rendered)


def _render_agent_rules(value: Any) -> str:
    if isinstance(value, dict):
        return "\n".join(f"- {key}: {item}" for key, item in value.items())
    return _text_value(value)


def _section(title: str, body: str) -> str:
    body = body.strip()
    if not body:
        return ""
    tag = title.lower().replace(" ", "_")
    return f"<{tag}>\n{body}\n</{tag}>"


def _text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
