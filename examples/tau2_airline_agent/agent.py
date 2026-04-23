"""Editable harness bundle for the tau2 airline experiment."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def build_harness_bundle() -> dict[str, object]:
    root = Path(__file__).resolve().parent
    controller_path = root / "controller.py"
    controller_module = _load_module("autoharness_tau2_controller", controller_path)
    controller_contract = controller_module.runtime_controller_contract()
    if not isinstance(controller_contract, dict):
        raise TypeError("controller.runtime_controller_contract() must return a dict.")
    return {
        "system_prompt": (root / "system_prompt.md").read_text(encoding="utf-8"),
        "policy_prompt": (root / "policy_prompt.md").read_text(encoding="utf-8"),
        "tool_instructions": (root / "tool_instructions.md").read_text(encoding="utf-8"),
        "skillbook_template": (root / "skillbook_template.md").read_text(encoding="utf-8"),
        "reflector_prompt": (root / "reflector_prompt.md").read_text(encoding="utf-8"),
        "skill_manager_prompt": (root / "skill_manager_prompt.md").read_text(encoding="utf-8"),
        "controller_source": controller_path.read_text(encoding="utf-8"),
        "controller_contract": _json_safe(controller_contract),
    }


def build_agent() -> dict[str, object]:
    return {
        "kind": "tau2_airline_harness",
        "bundle": build_harness_bundle(),
    }


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value
