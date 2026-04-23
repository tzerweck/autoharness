"""Lexical retrieval and formatting helpers for ACE-static."""

from __future__ import annotations

import re

from .schemas import SkillRecord
from .skill_store import skill_search_text

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "between",
    "book",
    "booking",
    "bookings",
    "can",
    "could",
    "customer",
    "details",
    "do",
    "for",
    "from",
    "help",
    "i",
    "id",
    "identify",
    "if",
    "in",
    "information",
    "it",
    "me",
    "modify",
    "modifying",
    "my",
    "not",
    "no",
    "number",
    "only",
    "of",
    "on",
    "or",
    "please",
    "provide",
    "provided",
    "provides",
    "request",
    "requests",
    "reservation",
    "reservations",
    "retrieve",
    "retrieving",
    "same",
    "specific",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "travel",
    "trip",
    "under",
    "user",
    "users",
    "way",
    "when",
    "with",
    "without",
    "you",
    "your",
    "flight",
    "flights",
}

_FIELD_CHAR_LIMITS = {
    "when_to_apply": 110,
    "guidance": 220,
    "caution": 140,
}


def rank_skills(skills: list[SkillRecord], query_text: str) -> list[tuple[int, SkillRecord]]:
    query_tokens = set(_tokenize(query_text))
    ranked: list[tuple[int, SkillRecord]] = []
    if not query_tokens:
        return ranked
    for skill in skills:
        score = len(query_tokens & set(_tokenize(skill_search_text(skill))))
        if score > 0:
            ranked.append((score, skill))
    ranked.sort(
        key=lambda item: (
            item[0],
            item[1].title.lower(),
            item[1].guidance.lower(),
        ),
        reverse=True,
    )
    return ranked


def format_skill_block(
    template: str,
    skills: list[SkillRecord],
    *,
    max_chars: int,
) -> str:
    if not skills:
        return template.format(
            skill_count=0,
            skills_block="- No relevant prior skills were retrieved for this episode.",
        ).strip()

    rendered_skills: list[str] = []
    omitted_count = 0
    for index, skill in enumerate(skills, start=1):
        block = _render_skill(index, skill)
        candidate_skills = "\n".join(rendered_skills + [block])
        candidate = template.format(
            skill_count=len(rendered_skills) + 1,
            skills_block=candidate_skills,
        ).strip()
        if max_chars > 0 and len(candidate) > max_chars:
            if not rendered_skills:
                rendered_skills.append(_render_skill(index, skill, compact=True))
            omitted_count = len(skills) - len(rendered_skills)
            break
        rendered_skills.append(block)

    rendered = template.format(
        skill_count=len(rendered_skills),
        skills_block="\n".join(rendered_skills),
    ).strip()
    if omitted_count > 0:
        rendered += "\n\n[Additional retrieved skills omitted due to budget.]"
    if max_chars > 0 and len(rendered) > max_chars:
        clipped = rendered[: max_chars - 72].rstrip()
        rendered = clipped + "\n\n[Skill block clipped to fit the configured budget.]"
    return rendered


def _tokenize(value: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", value.lower())
    return [
        token
        for token in tokens
        if (token.isdigit() or len(token) > 1) and token not in _STOPWORDS
    ]


def _render_skill(index: int, skill: SkillRecord, *, compact: bool = False) -> str:
    when_to_apply = _truncate(skill.when_to_apply, _FIELD_CHAR_LIMITS["when_to_apply"])
    guidance_limit = 160 if compact else _FIELD_CHAR_LIMITS["guidance"]
    caution_limit = 100 if compact else _FIELD_CHAR_LIMITS["caution"]
    guidance = _truncate(skill.guidance, guidance_limit)
    caution = _truncate(skill.caution, caution_limit)

    lines = [
        f"{index}. {skill.title}",
        f"   When: {when_to_apply}",
        f"   Do: {guidance}",
    ]
    if caution:
        lines.append(f"   Watch out: {caution}")
    return "\n".join(lines)


def _truncate(value: str, max_chars: int) -> str:
    value = value.strip()
    if max_chars <= 0 or len(value) <= max_chars:
        return value
    clipped = value[: max_chars - 3].rstrip()
    if " " in clipped:
        clipped = clipped.rsplit(" ", 1)[0]
    return clipped.rstrip(",;:. ") + "..."
