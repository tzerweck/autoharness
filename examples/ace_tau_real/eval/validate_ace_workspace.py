from __future__ import annotations

import importlib
import json
from pathlib import Path


MODULES = [
    "ace",
    "ace.implementations.agent",
    "ace.implementations.prompts",
    "ace.implementations.reflector",
    "ace.implementations.skill_manager",
    "ace.implementations.helpers",
    "ace.implementations.skill_rendering",
    "ace.core.skillbook",
    "ace.deduplication.manager",
    "ace.deduplication.operations",
    "ace.steps.update",
    "ace.steps.deduplicate",
]


def main() -> int:
    imported: list[str] = []
    for module_name in MODULES:
        importlib.import_module(module_name)
        imported.append(module_name)

    from ace import Skillbook

    payload = {
        "workspace_root": str(Path.cwd()),
        "modules_imported": imported,
        "skillbook_type": type(Skillbook()).__name__,
    }
    print(json.dumps(payload, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
