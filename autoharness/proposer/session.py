"""Proposer session persistence helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autoharness.store.writer import write_json, write_text


def snapshot_editable_contents(editable_paths: list[Path]) -> dict[Path, str]:
    snapshot: dict[Path, str] = {}
    for path in editable_paths:
        if path.is_dir():
            for file_path in sorted(path.rglob("*")):
                if file_path.is_file():
                    snapshot[file_path] = file_path.read_text(encoding="utf-8")
            continue
        if path.exists():
            snapshot[path] = path.read_text(encoding="utf-8")
    return snapshot


def detect_changed_files(before: dict[Path, str], editable_paths: list[Path]) -> list[Path]:
    after = snapshot_editable_contents(editable_paths)
    changed_files = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) != after.get(path):
            changed_files.append(path)
    return changed_files


def load_structured_proposer_result(root: Path, filename: str) -> dict[str, Any]:
    result_path = root / "contract" / filename
    if not result_path.exists():
        fallback_path = root / filename
        if not fallback_path.exists():
            return {}
        result_path = fallback_path
    try:
        return json.loads(result_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"result_parse_error": f"Invalid JSON in {result_path}"}


def write_proposer_session_artifacts(
    destination_dir: Path,
    *,
    stdout: str,
    stderr: str,
    metadata: dict[str, Any],
) -> None:
    write_text(destination_dir / "stdout.txt", stdout)
    write_text(destination_dir / "stderr.txt", stderr)
    write_json(destination_dir / "session.json", metadata)
