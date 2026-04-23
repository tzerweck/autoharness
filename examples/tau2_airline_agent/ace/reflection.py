"""Reflector step for ACE-static."""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from .schemas import SkillRecord, skills_to_dicts

CallTextModel = Callable[[str, str, str, dict[str, Any] | None, str], str]


def should_reflect(settings: dict[str, Any], mean_reward: float) -> bool:
    if mean_reward >= 1.0:
        return bool(settings.get("reflect_on_success", True))
    return bool(settings.get("reflect_on_failure", True))


def propose_skills(
    *,
    case_id: str,
    simulations: list[Any],
    mean_reward: float,
    reflector_prompt: str,
    model: str,
    llm_args: dict[str, Any] | None,
    max_skills: int,
    call_text_model: CallTextModel,
) -> dict[str, Any]:
    summary = summarize_simulations(simulations)
    system_prompt = reflector_prompt.format(max_skills=max_skills)
    user_prompt = (
        f"Case ID: {case_id}\n"
        f"Mean reward: {mean_reward:.3f}\n\n"
        f"Episode summary:\n{summary}\n\n"
        "Return JSON only."
    )
    raw_response = call_text_model(
        model,
        system_prompt,
        user_prompt,
        llm_args,
        "ace_reflector",
    )
    payload = _extract_json_payload(raw_response)
    proposed_skills = [
        SkillRecord(
            skill_id=f"skill_{uuid.uuid4().hex[:10]}",
            title=str(item.get("title", "")).strip(),
            when_to_apply=str(item.get("when_to_apply", "")).strip(),
            guidance=str(item.get("guidance", "")).strip(),
            caution=str(item.get("caution", "")).strip(),
            evidence_case_ids=[case_id],
            source="reflector",
        )
        for item in payload.get("skills", [])
        if isinstance(item, dict)
    ]
    return {
        "summary": summary,
        "raw_response": raw_response,
        "proposed_skills": skills_to_dicts(proposed_skills),
    }


def summarize_simulations(simulations: list[Any], *, max_messages: int = 32, max_chars: int = 7000) -> str:
    lines: list[str] = []
    for sim in simulations:
        task_id = getattr(sim, "task_id", "unknown")
        reward = getattr(getattr(sim, "reward_info", None), "reward", None)
        termination_reason = getattr(sim, "termination_reason", "unknown")
        lines.append(f"Task {task_id} | reward={reward} | termination={termination_reason}")

        messages = []
        if hasattr(sim, "get_messages"):
            try:
                messages = list(sim.get_messages())
            except Exception:
                messages = list(getattr(sim, "messages", []) or [])
        else:
            messages = list(getattr(sim, "messages", []) or [])
        for message in messages[:max_messages]:
            role = getattr(message, "role", "unknown")
            if hasattr(role, "value"):
                role = role.value
            text = _message_preview(message)
            lines.append(f"[{role}] {text}")
        lines.append("")
    rendered = "\n".join(lines).strip()
    return rendered[:max_chars]


def _message_preview(message: Any) -> str:
    content = getattr(message, "content", None)
    if content:
        return str(content).replace("\n", " ")[:240]
    tool_calls = getattr(message, "tool_calls", None) or []
    if tool_calls:
        names = [str(getattr(call, "name", "tool")) for call in tool_calls]
        return f"tool_calls={names}"
    return "(no text)"


def _extract_json_payload(raw_response: str) -> dict[str, Any]:
    raw_response = raw_response.strip()
    if not raw_response:
        return {"skills": []}
    try:
        payload = json.loads(raw_response)
        return payload if isinstance(payload, dict) else {"skills": []}
    except json.JSONDecodeError:
        pass

    start = raw_response.find("{")
    end = raw_response.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"skills": []}
    try:
        payload = json.loads(raw_response[start : end + 1])
        return payload if isinstance(payload, dict) else {"skills": []}
    except json.JSONDecodeError:
        return {"skills": []}
