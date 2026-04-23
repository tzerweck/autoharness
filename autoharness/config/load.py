"""Parsing and loading for experiment configs."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

from autoharness.config.models import (
    ExperimentConfig,
)
from autoharness.config.normalize import normalize_experiment_config
from autoharness.errors import ConfigError


def load_experiment_config(config_path: Path) -> ExperimentConfig:
    path = config_path.expanduser().resolve()
    if not path.exists():
        raise ConfigError(f"Config file does not exist: {path}")

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    experiment = raw.get("experiment", {})
    if not experiment:
        raise ConfigError("Missing required [experiment] section.")

    payload = {
        "name": experiment.get("name"),
        "workspace_root": experiment.get("workspace_root"),
        "output_root": experiment.get("output_root", "runs"),
        "stack": experiment.get("stack", "python"),
        "max_iterations": experiment.get("max_iterations", 10),
        "proposer": raw.get("proposer", {}),
        "runner": raw.get("runner", {}),
        "policy": raw.get("policy", {}),
        "validation": raw.get("validation", {}),
        "surfaces": _prepare_surfaces(raw.get("surfaces", {})),
        "cases": raw.get("cases", []),
        "context": raw.get("context", {}),
        "reporting": raw.get("reporting", {}),
        "config_path": path,
    }
    try:
        config = ExperimentConfig.model_validate(payload)
    except Exception as exc:
        raise ConfigError(f"Invalid experiment config: {exc}") from exc
    return normalize_experiment_config(config)


def load_saved_experiment_config(experiment_json_path: Path) -> ExperimentConfig:
    path = experiment_json_path.expanduser().resolve()
    if not path.exists():
        raise ConfigError(f"Saved experiment file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        config = ExperimentConfig.model_validate(payload)
    except Exception as exc:
        raise ConfigError(f"Invalid saved experiment file: {exc}") from exc
    return normalize_experiment_config(config)


def _prepare_surfaces(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ConfigError("Expected [surfaces.<name>] tables.")

    surfaces: dict[str, Any] = {}
    for name, surface in raw.items():
        if not isinstance(surface, dict):
            raise ConfigError(f"Surface '{name}' must be declared as a table.")
        surfaces[name] = {"name": name, **surface}
    return surfaces
