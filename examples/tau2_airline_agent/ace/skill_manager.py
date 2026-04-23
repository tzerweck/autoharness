"""SkillManager step for ACE-static."""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from .schemas import SkillRecord, skills_to_dicts

CallTextModel = Callable[[str, str, str, dict[str, Any] | None, str], str]


def review_skill_candidates(
    *,
    existing_skills: list[SkillRecord],
    proposed_skills: list[SkillRecord],
    skill_manager_prompt: str,
    model: str,
    llm_args: dict[str, Any] | None,
    max_accept: int,
    max_store_context_skills: int,
    call_text_model: CallTextModel,
) -> dict[str, Any]:
    if not proposed_skills:
        return {
            "accepted_skills": [],
            "rejected_titles": [],
            "notes": "No proposed skills.",
            "raw_response": "",
        }

    system_prompt = skill_manager_prompt.format(max_accept=max_accept)
    user_prompt = (
        f"Current store sample:\n"
        f"{json.dumps(skills_to_dicts(existing_skills[:max_store_context_skills]), indent=2)}\n\n"
        f"Proposed skills:\n{json.dumps(skills_to_dicts(proposed_skills), indent=2)}\n\n"
        "Return JSON only."
    )
    raw_response = call_text_model(
        model,
        system_prompt,
        user_prompt,
        llm_args,
        "ace_skill_manager",
    )
    payload = _extract_json_payload(raw_response)
    accepted = [
        SkillRecord(
            skill_id=f"skill_{uuid.uuid4().hex[:10]}",
            title=str(item.get("title", "")).strip(),
            when_to_apply=str(item.get("when_to_apply", "")).strip(),
            guidance=str(item.get("guidance", "")).strip(),
            caution=str(item.get("caution", "")).strip(),
            evidence_case_ids=[],
            source="skill_manager",
        )
        for item in payload.get("accepted", [])
        if isinstance(item, dict)
    ]
    return {
        "accepted_skills": skills_to_dicts(accepted[:max_accept]),
        "rejected_titles": [str(item) for item in payload.get("rejected_titles", [])],
        "notes": str(payload.get("notes", "")),
        "raw_response": raw_response,
    }


def _extract_json_payload(raw_response: str) -> dict[str, Any]:
    raw_response = raw_response.strip()
    if not raw_response:
        return {"accepted": []}
    try:
        payload = json.loads(raw_response)
        return payload if isinstance(payload, dict) else {"accepted": []}
    except json.JSONDecodeError:
        pass

    start = raw_response.find("{")
    end = raw_response.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"accepted": []}
    try:
        payload = json.loads(raw_response[start : end + 1])
        return payload if isinstance(payload, dict) else {"accepted": []}
    except json.JSONDecodeError:
        return {"accepted": []}
