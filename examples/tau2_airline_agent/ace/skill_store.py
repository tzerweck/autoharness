"""Persistence and merge helpers for ACE-static skill stores."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .schemas import SkillRecord, skill_from_dict, skills_to_dicts


def load_skill_records(path: Path) -> list[SkillRecord]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Expected a list of skills at {path}")
    return [skill_from_dict(item) for item in payload if isinstance(item, dict)]


def save_skill_records(path: Path, skills: list[SkillRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(skills_to_dicts(skills), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def merge_skill_records(
    existing: list[SkillRecord],
    additions: list[SkillRecord],
    *,
    max_store_size: int,
) -> list[SkillRecord]:
    merged = list(existing)
    for addition in additions:
        if not addition.title or not addition.guidance:
            continue
        match_index = _find_merge_target(merged, addition)
        if match_index is None:
            merged.append(addition)
            continue
        merged[match_index] = _merge_pair(merged[match_index], addition)
    if max_store_size > 0 and len(merged) > max_store_size:
        merged = merged[-max_store_size:]
    return merged


def skill_search_text(skill: SkillRecord) -> str:
    return " ".join(
        part
        for part in (
            skill.title,
            skill.when_to_apply,
            skill.guidance,
            skill.caution,
        )
        if part
    )


def _find_merge_target(existing: list[SkillRecord], candidate: SkillRecord) -> int | None:
    candidate_title = _normalize(candidate.title)
    candidate_tokens = set(_tokenize(skill_search_text(candidate)))
    for index, item in enumerate(existing):
        if _normalize(item.title) == candidate_title:
            return index
        existing_tokens = set(_tokenize(skill_search_text(item)))
        if existing_tokens and candidate_tokens:
            overlap = len(existing_tokens & candidate_tokens) / min(
                len(existing_tokens),
                len(candidate_tokens),
            )
            if overlap >= 0.8:
                return index
    return None


def _merge_pair(left: SkillRecord, right: SkillRecord) -> SkillRecord:
    evidence = []
    for item in left.evidence_case_ids + right.evidence_case_ids:
        if item not in evidence:
            evidence.append(item)
    return SkillRecord(
        skill_id=left.skill_id or right.skill_id,
        title=_prefer_longer(left.title, right.title),
        when_to_apply=_prefer_longer(left.when_to_apply, right.when_to_apply),
        guidance=_prefer_longer(left.guidance, right.guidance),
        caution=_prefer_longer(left.caution, right.caution),
        evidence_case_ids=evidence,
        source=left.source or right.source,
    )


def _prefer_longer(left: str, right: str) -> str:
    left = left.strip()
    right = right.strip()
    return right if len(right) > len(left) else left


def _normalize(value: str) -> str:
    return " ".join(_tokenize(value))


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.lower())
