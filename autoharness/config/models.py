"""Pydantic models representing experiment configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AutoharnessModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class SurfaceConfigBase(AutoharnessModel):
    name: str
    target: str
    description: str | None = None
    read_only: bool = False


class WorkspaceFileSurfaceConfig(SurfaceConfigBase):
    kind: Literal["workspace_file"]
    filename: str
    base_file: Path


class WorkspaceTreeSurfaceConfig(SurfaceConfigBase):
    kind: Literal["workspace_tree"]
    base_dir: Path


class ModuleAttrSurfaceConfig(SurfaceConfigBase):
    kind: Literal["module_attr"]
    module: str
    attribute: str
    base_value: str
    emit_file: str
    value_format: Literal["text", "python_expr"] = "text"


SurfaceConfig = Annotated[
    WorkspaceFileSurfaceConfig | WorkspaceTreeSurfaceConfig | ModuleAttrSurfaceConfig,
    Field(discriminator="kind"),
]


class CaseConfig(AutoharnessModel):
    id: str
    split: Literal["train", "holdout", "scorecard"]
    runner_ref: str
    stratum: str | None = None
    weight: float = 1.0
    tags: list[str] = Field(default_factory=list)
    timeout_sec: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyConfig(AutoharnessModel):
    primary_metric: Literal["pass_rate", "mean_score"] = "pass_rate"
    secondary_metrics: list[str] = Field(default_factory=list)
    screen_split: Literal["train"] = "train"
    holdout_every: int = 3
    require_holdout_for_promotion: bool = True
    min_primary_improvement: float = 0.0
    allow_tie_if_secondary_improves: bool = True
    prefer_simpler_on_tie: bool = True
    max_allowed_holdout_regression: float = 0.0
    guardrail_case_ids_file: Path | None = None
    max_allowed_guardrail_regressions: int = 0
    keep_top_k_visible_candidates: int = 20


class ValidationConfig(AutoharnessModel):
    kind: Literal["python_import", "script"] = "python_import"
    entrypoint: str | None = None
    script: list[str] | None = None
    timeout_sec: float = 30.0


class ProposerConfig(AutoharnessModel):
    backend: Literal["manual", "command"] = "manual"
    max_turns: int = 50
    timeout_sec: float | None = None
    command: list[str] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    system_prompt_file: Path | None = None
    manual_source_dir: Path | None = None
    result_filename: str = "proposer_result.json"


class PytestRunnerConfig(AutoharnessModel):
    execution_mode: Literal["per_case", "batch"] = "per_case"
    pytest_args: list[str] = Field(default_factory=list)
    artifact_dir_env: str = "AUTOHARNESS_ARTIFACT_DIR"
    candidate_dir_env: str = "AUTOHARNESS_CANDIDATE_DIR"
    report_json_path: str = ".autoharness_pytest_report.json"
    junit_xml_path: str | None = None


class ScriptRunnerConfig(AutoharnessModel):
    command: list[str]
    result_json_path: str


class RunnerConfig(AutoharnessModel):
    kind: Literal["pytest", "script"] = "pytest"
    project_root: Path | None = None
    env: dict[str, str] = Field(default_factory=dict)
    pytest: PytestRunnerConfig | None = None
    script: ScriptRunnerConfig | None = None


class ContextConfig(AutoharnessModel):
    history_strategy: str = "recent_plus_best"
    max_candidates: int = 8
    max_failed_cases_per_candidate: int = 5
    include_diffs: bool = True
    include_train_traces: bool = True
    include_holdout_details: bool = False
    emit_manifest: bool = True


class ReportingConfig(AutoharnessModel):
    emit_markdown: bool = True
    emit_json: bool = True


class ExperimentConfig(AutoharnessModel):
    name: str
    workspace_root: Path
    output_root: Path
    stack: Literal["python"] = "python"
    max_iterations: int = 10
    proposer: ProposerConfig = Field(default_factory=ProposerConfig)
    runner: RunnerConfig = Field(default_factory=RunnerConfig)
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    surfaces: dict[str, SurfaceConfig]
    cases: list[CaseConfig]
    context: ContextConfig = Field(default_factory=ContextConfig)
    reporting: ReportingConfig = Field(default_factory=ReportingConfig)
    config_path: Path

    @model_validator(mode="after")
    def _validate_shape(self) -> "ExperimentConfig":
        if not self.cases:
            raise ValueError("Expected at least one [[cases]] entry.")
        if not self.surfaces:
            raise ValueError("Expected at least one [surfaces.<name>] entry.")
        return self
