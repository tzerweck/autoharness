"""Small schemas for ACE-static runtime state."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillRecord:
    skill_id: str
    title: str
    when_to_apply: str
    guidance: str
    caution: str = ""
    evidence_case_ids: list[str] = field(default_factory=list)
    source: str = "reflector"


def skill_from_dict(payload: dict[str, Any]) -> SkillRecord:
    return SkillRecord(
        skill_id=str(payload.get("skill_id", "")),
        title=str(payload.get("title", "")).strip(),
        when_to_apply=str(payload.get("when_to_apply", "")).strip(),
        guidance=str(payload.get("guidance", "")).strip(),
        caution=str(payload.get("caution", "")).strip(),
        evidence_case_ids=[str(item) for item in payload.get("evidence_case_ids", [])],
        source=str(payload.get("source", "reflector")).strip() or "reflector",
    )


def skill_to_dict(skill: SkillRecord) -> dict[str, Any]:
    return asdict(skill)


def skills_to_dicts(skills: list[SkillRecord]) -> list[dict[str, Any]]:
    return [skill_to_dict(skill) for skill in skills]
