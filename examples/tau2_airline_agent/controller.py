"""Controller config surface for the tau2 airline harness."""

from __future__ import annotations


def runtime_controller_contract() -> dict[str, object]:
    return {
        "mode": "ace_static",
        "agent_rules": {
            "confirmation_rule": "Confirm before irreversible itinerary changes or cancellations.",
            "clarification_rule": "Ask one direct clarification question when required fields are missing.",
            "tool_rule": "Prefer exact tool use over free-form policy speculation.",
            "stop_rule": "Stop once the customer goal is resolved or a policy block is clearly explained.",
        },
        "ace_static": {
            "top_k": 1,
            "retrieval_min_overlap": 2,
            "max_skill_block_chars": 900,
            "reflect_on_success": False,
            "reflect_on_failure": True,
            "max_reflector_skills": 1,
            "max_manager_accepted_skills": 1,
            "max_store_size": 16,
            "max_store_context_skills": 8,
        },
    }
