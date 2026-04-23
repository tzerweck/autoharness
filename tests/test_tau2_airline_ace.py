from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


EXAMPLE_ROOT = Path("examples/tau2_airline_agent").resolve()


def test_tau2_airline_bundle_includes_ace_prompts_and_controller() -> None:
    agent_module = _load_module("tau2_airline_agent_bundle", EXAMPLE_ROOT / "agent.py")

    bundle = agent_module.build_harness_bundle()

    assert bundle["controller_contract"]["mode"] == "ace_static"
    assert "agent_rules" in bundle["controller_contract"]
    assert "skillbook_template" in bundle
    assert "reflector_prompt" in bundle
    assert "skill_manager_prompt" in bundle


def test_ace_runtime_resolves_mode_and_reads_train_store(tmp_path: Path) -> None:
    ace_runtime = _import_example_module("ace.runtime")
    skill_store = _import_example_module("ace.skill_store")
    schemas = _import_example_module("ace.schemas")

    case_output_dir = tmp_path / "eval" / "train" / "tau2_runs" / "case_001"
    state_root = tmp_path / "eval" / "ace_state"
    state_root.mkdir(parents=True)
    skill_store.save_skill_records(
        state_root / "train_live.json",
        [
            schemas.SkillRecord(
                skill_id="skill_1",
                title="Confirm before canceling",
                when_to_apply="The user asks for a cancellation or itinerary change.",
                guidance="Confirm the exact booking and the intended irreversible action before invoking the cancel tool.",
                caution="Do not assume the user wants cancellation just because they mention frustration.",
                evidence_case_ids=["train.airline_0001"],
            )
        ],
    )
    bundle = {
        "controller_contract": {
            "mode": "ace_static",
            "agent_rules": {"stop_rule": "Stop when the task is resolved."},
            "ace_static": {
                "top_k": 3,
                "retrieval_min_overlap": 1,
                "max_skill_block_chars": 1200,
            },
        },
        "skillbook_template": "Retrieved ({skill_count})\n{skills_block}",
    }

    episode = ace_runtime.prepare_episode_context(
        harness_bundle=bundle,
        case_output_dir=case_output_dir,
        split="train",
        case_id="train.airline_0002",
        first_user_message_text="I want to cancel my booking and get a refund.",
    )

    assert episode["mode"] == "ace_static"
    assert len(episode["retrieved_skills"]) == 1
    assert "Confirm before canceling" in episode["skill_block"]
    assert (
        ace_runtime.resolve_runtime_mode(
            bundle["controller_contract"],
            {"AUTOHARNESS_TAU2_MODE_OVERRIDE": "plain"},
        )
        == "plain"
    )


def test_ace_runtime_updates_train_snapshot_with_reflector_and_manager(tmp_path: Path) -> None:
    ace_runtime = _import_example_module("ace.runtime")

    case_output_dir = tmp_path / "eval" / "train" / "tau2_runs" / "case_001"
    case_output_dir.mkdir(parents=True)
    bundle = {
        "controller_contract": {
            "mode": "ace_static",
            "ace_static": {
                "reflect_on_success": True,
                "reflect_on_failure": True,
                "max_reflector_skills": 2,
                "max_manager_accepted_skills": 2,
                "max_store_size": 10,
                "max_store_context_skills": 4,
            },
        },
        "reflector_prompt": "Return at most {max_skills} skills as JSON.",
        "skill_manager_prompt": "Accept at most {max_accept} skills as JSON.",
    }
    call_count = {"value": 0}

    def fake_call_text_model(model, system_prompt, user_prompt, llm_args, call_name):
        call_count["value"] += 1
        if call_name == "ace_reflector":
            return (
                '{"skills": [{"title": "Confirm booking before canceling", '
                '"when_to_apply": "When the user requests a cancellation", '
                '"guidance": "Read back the itinerary and confirm the exact action before using cancel tools.", '
                '"caution": "Avoid irreversible changes before confirmation."}]}'
            )
        return (
            '{"accepted": [{"title": "Confirm booking before canceling", '
            '"when_to_apply": "When the user requests a cancellation", '
            '"guidance": "Read back the itinerary and confirm the exact action before using cancel tools.", '
            '"caution": "Avoid irreversible changes before confirmation."}], '
            '"rejected_titles": [], "notes": "accepted"}'
        )

    class FakeRewardInfo:
        reward = 1.0

    class FakeMessage:
        def __init__(self, role: str, content: str) -> None:
            self.role = role
            self.content = content
            self.tool_calls = None

    class FakeSimulation:
        task_id = "1"
        reward_info = FakeRewardInfo()
        termination_reason = "completed"

        def get_messages(self):
            return [
                FakeMessage("user", "Please cancel my trip."),
                FakeMessage("assistant", "I can help with that."),
            ]

    artifact = ace_runtime.maybe_update_skill_store(
        harness_bundle=bundle,
        case_output_dir=case_output_dir,
        split="train",
        case_id="train.airline_0001",
        simulations=[FakeSimulation()],
        mean_reward=1.0,
        reflector_model="test-model",
        skill_manager_model="test-model",
        reflector_llm_args=None,
        skill_manager_llm_args=None,
        call_text_model=fake_call_text_model,
    )

    snapshot_path = tmp_path / "eval" / "ace_state" / "train_snapshot.json"
    assert snapshot_path.exists()
    assert artifact["updated"] is True
    assert artifact["store_after_count"] == 1
    assert call_count["value"] == 2


def test_ace_retrieval_ignores_generic_airline_overlap() -> None:
    retrieval = _import_example_module("ace.retrieval")
    schemas = _import_example_module("ace.schemas")

    query = (
        "I want to book the exact same flight again and I only have my user ID, "
        "not the reservation ID."
    )
    skills = [
        schemas.SkillRecord(
            skill_id="skill_generic",
            title="Identify reservation by flight number when no reservation ID is provided",
            when_to_apply="when a user provides a flight number but not a reservation ID",
            guidance="retrieve all reservations linked to the user's ID and filter them by the flight number",
            caution="do not assume a unique reservation matches the flight number",
        )
    ]

    assert retrieval.rank_skills(skills, query) == []


def test_ace_skill_block_omits_extra_skills_instead_of_mid_sentence_truncation() -> None:
    retrieval = _import_example_module("ace.retrieval")
    schemas = _import_example_module("ace.schemas")

    template = "Retrieved skills ({skill_count}):\n{skills_block}"
    skills = [
        schemas.SkillRecord(
            skill_id="skill_one",
            title="Specific skill one",
            when_to_apply="when a specific trigger appears in the user request",
            guidance="follow a detailed but bounded procedure that still fits in budget",
            caution="do not generalize this beyond the matching trigger",
        ),
        schemas.SkillRecord(
            skill_id="skill_two",
            title="Specific skill two",
            when_to_apply="when another trigger appears",
            guidance="take a second action",
            caution="avoid over-applying it",
        ),
    ]

    rendered = retrieval.format_skill_block(template, skills, max_chars=260)

    assert "Specific skill one" in rendered
    assert "Specific skill two" not in rendered
    assert "omitted due to budget" in rendered or "clipped to fit the configured budget" in rendered


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _import_example_module(module_name: str):
    sys.modules.pop("ace", None)
    sys.modules.pop(module_name, None)
    sys.path.insert(0, str(EXAMPLE_ROOT))
    try:
        return importlib.import_module(module_name)
    finally:
        sys.path.pop(0)
