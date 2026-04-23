"""Normalization and cross-field validation for experiment configs."""

from __future__ import annotations

from pathlib import Path

from autoharness.config.models import (
    ExperimentConfig,
    ModuleAttrSurfaceConfig,
    RunnerConfig,
    SurfaceConfig,
    WorkspaceFileSurfaceConfig,
    WorkspaceTreeSurfaceConfig,
)
from autoharness.constants import DEFAULT_RUNS_DIRNAME
from autoharness.errors import ConfigError


def normalize_experiment_config(config: ExperimentConfig) -> ExperimentConfig:
    config_dir = config.config_path.parent
    workspace_root = _resolve_path(config_dir, config.workspace_root)
    output_root = _resolve_output_root(config_dir, config.output_root)
    runner = _normalize_runner(config.runner, workspace_root)
    proposer = _normalize_proposer(config.proposer, config_dir)
    policy = _normalize_policy(config.policy, config_dir)
    surfaces = _normalize_surfaces(config.surfaces, workspace_root)

    normalized = config.model_copy(
        update={
            "workspace_root": workspace_root,
            "output_root": output_root,
            "runner": runner,
            "proposer": proposer,
            "policy": policy,
            "surfaces": surfaces,
        }
    )
    _validate_config(normalized)
    return normalized


def _normalize_runner(runner: RunnerConfig, workspace_root: Path) -> RunnerConfig:
    project_root = runner.project_root
    if project_root is not None:
        project_root = _resolve_path(workspace_root, project_root)
    else:
        project_root = workspace_root
    return runner.model_copy(update={"project_root": project_root})


def _normalize_proposer(proposer, config_dir: Path):
    updates = {}
    if proposer.system_prompt_file is not None:
        updates["system_prompt_file"] = _resolve_path(config_dir, proposer.system_prompt_file)
    if proposer.manual_source_dir is not None:
        updates["manual_source_dir"] = _resolve_path(config_dir, proposer.manual_source_dir)
    if not updates:
        return proposer
    return proposer.model_copy(update=updates)


def _normalize_policy(policy, config_dir: Path):
    updates = {}
    if policy.guardrail_case_ids_file is not None:
        updates["guardrail_case_ids_file"] = _resolve_path(
            config_dir, policy.guardrail_case_ids_file
        )
    if not updates:
        return policy
    return policy.model_copy(update=updates)


def _normalize_surfaces(
    surfaces: dict[str, SurfaceConfig], workspace_root: Path
) -> dict[str, SurfaceConfig]:
    normalized: dict[str, SurfaceConfig] = {}
    for name, surface in surfaces.items():
        if isinstance(surface, WorkspaceFileSurfaceConfig):
            normalized[name] = surface.model_copy(
                update={"base_file": _resolve_path(workspace_root, surface.base_file)}
            )
            continue
        if isinstance(surface, WorkspaceTreeSurfaceConfig):
            normalized[name] = surface.model_copy(
                update={"base_dir": _resolve_path(workspace_root, surface.base_dir)}
            )
            continue
        if isinstance(surface, ModuleAttrSurfaceConfig):
            normalized[name] = surface
            continue
        raise ConfigError(f"Unsupported surface config type for '{name}'.")
    return normalized


def _validate_config(config: ExperimentConfig) -> None:
    if not config.workspace_root.exists() or not config.workspace_root.is_dir():
        raise ConfigError(f"workspace_root must be an existing directory: {config.workspace_root}")

    if config.runner.project_root is None:
        raise ConfigError("runner.project_root normalization failed.")
    if not config.runner.project_root.exists():
        raise ConfigError(f"runner.project_root does not exist: {config.runner.project_root}")

    if config.validation.kind == "python_import" and not config.validation.entrypoint:
        raise ConfigError("validation.kind='python_import' requires validation.entrypoint.")

    if config.proposer.backend == "command" and not config.proposer.command:
        raise ConfigError("proposer.backend='command' requires proposer.command.")

    if not any(case.split == "train" for case in config.cases):
        raise ConfigError("Expected at least one train case.")

    for name, surface in config.surfaces.items():
        if isinstance(surface, WorkspaceFileSurfaceConfig) and not surface.base_file.exists():
            raise ConfigError(f"Surface '{name}' base_file does not exist: {surface.base_file}")
        if isinstance(surface, WorkspaceTreeSurfaceConfig):
            if not surface.base_dir.exists():
                raise ConfigError(f"Surface '{name}' base_dir does not exist: {surface.base_dir}")
            if not surface.base_dir.is_dir():
                raise ConfigError(f"Surface '{name}' base_dir must be a directory: {surface.base_dir}")

    if config.proposer.system_prompt_file and not config.proposer.system_prompt_file.exists():
        raise ConfigError(
            f"system_prompt_file does not exist: {config.proposer.system_prompt_file}"
        )
    if config.policy.guardrail_case_ids_file and not config.policy.guardrail_case_ids_file.exists():
        raise ConfigError(
            f"guardrail_case_ids_file does not exist: {config.policy.guardrail_case_ids_file}"
        )
    if config.proposer.backend == "manual":
        if config.proposer.manual_source_dir and not config.proposer.manual_source_dir.exists():
            raise ConfigError(
                f"manual_source_dir does not exist: {config.proposer.manual_source_dir}"
            )


def _resolve_output_root(config_dir: Path, output_root: Path) -> Path:
    if str(output_root) == DEFAULT_RUNS_DIRNAME:
        return config_dir / DEFAULT_RUNS_DIRNAME
    return _resolve_path(config_dir, output_root)


def _resolve_path(base: Path, value: Path) -> Path:
    if value.is_absolute():
        return value
    return (base / value).resolve()
