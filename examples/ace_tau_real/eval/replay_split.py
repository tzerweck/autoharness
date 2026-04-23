"""Replay a configured split without running a full AutoHarness iteration loop."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FRAMEWORK_ROOT = Path(__file__).resolve().parents[3]
if str(FRAMEWORK_ROOT) not in sys.path:
    sys.path.insert(0, str(FRAMEWORK_ROOT))

from autoharness.config.load import load_experiment_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to experiment TOML.")
    parser.add_argument("--split", default="holdout", choices=["train", "holdout", "scorecard"])
    parser.add_argument("--output-dir", required=True, help="Replay output directory.")
    parser.add_argument(
        "--train-snapshot-skillbook",
        help="Path to train_snapshot_skillbook.json for ACE read-only holdout replays.",
    )
    parser.add_argument(
        "--override-trials",
        type=int,
        default=None,
        help="Override case metadata.num_trials for the replay.",
    )
    parser.add_argument(
        "--dotenv",
        help="Optional dotenv file to load before launching the replay.",
    )
    args = parser.parse_args()

    if args.dotenv:
        _load_simple_dotenv(Path(args.dotenv).expanduser().resolve())

    config = load_experiment_config(Path(args.config))
    split = args.split
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_cases: list[dict[str, object]] = []
    for case in config.cases:
        if case.split != split:
            continue
        metadata = dict(case.metadata)
        if args.override_trials is not None:
            metadata["num_trials"] = args.override_trials
        manifest_cases.append(
            {
                "id": case.id,
                "runner_ref": case.runner_ref,
                "split": case.split,
                "stratum": case.stratum,
                "weight": case.weight,
                "tags": list(case.tags),
                "timeout_sec": case.timeout_sec,
                "metadata": metadata,
            }
        )

    if not manifest_cases:
        raise SystemExit(f"No cases found for split '{split}' in {config.config_path}")

    manifest_path = output_dir / "cases_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest_cases, ensure_ascii=True, indent=2),
        encoding="utf-8",
    )

    state_root = output_dir.parent / "ace_state"
    if args.train_snapshot_skillbook:
        state_root.mkdir(parents=True, exist_ok=True)
        destination = state_root / "train_snapshot_skillbook.json"
        shutil.copyfile(Path(args.train_snapshot_skillbook).expanduser().resolve(), destination)

    env = dict(os.environ)
    env["AUTOHARNESS_WORKSPACE_ROOT"] = str(config.workspace_root)
    env["AUTOHARNESS_OUTPUT_DIR"] = str(output_dir)
    env["AUTOHARNESS_CASES_MANIFEST"] = str(manifest_path)
    env["AUTOHARNESS_RESULT_JSON_PATH"] = str(output_dir / "result.json")
    env["AUTOHARNESS_SPLIT"] = split
    for key, value in config.runner.env.items():
        env[key] = value

    script_command = config.runner.script.command if config.runner.script else None
    if not script_command:
        raise SystemExit("Replay utility only supports script runners.")

    command = [str(part) for part in script_command]
    completed = subprocess.run(
        command,
        cwd=config.runner.project_root or config.workspace_root,
        env=env,
        text=True,
    )
    return completed.returncode

def _load_simple_dotenv(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


if __name__ == "__main__":
    raise SystemExit(main())
