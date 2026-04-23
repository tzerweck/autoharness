from __future__ import annotations

import sys
from pathlib import Path

from autoharness.config.models import (
    CaseConfig,
    ContextConfig,
    ExperimentConfig,
    PolicyConfig,
    ProposerConfig,
    ReportingConfig,
    RunnerConfig,
    ScriptRunnerConfig,
    ValidationConfig,
    WorkspaceFileSurfaceConfig,
)
from autoharness.orchestration.baseline import run_baseline


def test_script_runner_baseline_executes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "agent.py").write_text("def build_agent():\n    return object()\n", encoding="utf-8")
    config = ExperimentConfig(
        name="script-runner-example",
        workspace_root=workspace,
        output_root=tmp_path / "runs",
        max_iterations=1,
        proposer=ProposerConfig(backend="manual", manual_source_dir=tmp_path / "unused"),
        runner=RunnerConfig(
            kind="script",
            project_root=workspace,
            script=ScriptRunnerConfig(
                command=[sys.executable, str(Path("tests/fixtures/script_eval.py").resolve())],
                result_json_path="result.json",
            ),
        ),
        policy=PolicyConfig(),
        validation=ValidationConfig(
            kind="script",
            script=[sys.executable, str(Path("tests/fixtures/validate_ok.py").resolve())],
        ),
        surfaces={
            "agent_entry": WorkspaceFileSurfaceConfig(
                name="agent_entry",
                kind="workspace_file",
                target="agent.py",
                filename="agent.py",
                base_file=workspace / "agent.py",
            )
        },
        cases=[
            CaseConfig(id="train.pass", split="train", runner_ref="case/train/pass"),
            CaseConfig(id="train.fail", split="train", runner_ref="case/train/fail"),
            CaseConfig(id="holdout.pass", split="holdout", runner_ref="case/holdout/pass"),
        ],
        context=ContextConfig(),
        reporting=ReportingConfig(),
        config_path=tmp_path / "inline.toml",
    )

    result = run_baseline(config)

    assert result.validation.ok is True
    assert result.train is not None
    assert result.train.summary.n_cases == 2
    assert result.train.summary.n_passed == 1
    assert result.holdout is not None
    assert result.holdout.summary.n_passed == 1


def test_script_runner_adds_framework_root_to_pythonpath(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "agent.py").write_text("def build_agent():\n    return object()\n", encoding="utf-8")

    script_path = tmp_path / "import_autoharness_eval.py"
    script_path.write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "import json",
                "import os",
                "from pathlib import Path",
                "",
                "from autoharness.integrations.tau2 import load_autoharness_case_manifest",
                "",
                "manifest = load_autoharness_case_manifest(Path(os.environ['AUTOHARNESS_CASES_MANIFEST']))",
                "result_path = Path(os.environ['AUTOHARNESS_RESULT_JSON_PATH'])",
                "split = os.environ['AUTOHARNESS_SPLIT']",
                "cases = [",
                "    {",
                "        'case_id': case.case_id,",
                "        'split': split,",
                "        'passed': True,",
                "        'score': 1.0,",
                "        'duration_sec': 0.01,",
                "        'metadata': {'task_id': case.task_id},",
                "    }",
                "    for case in manifest",
                "]",
                "summary = {",
                "    'split': split,",
                "    'n_cases': len(cases),",
                "    'n_passed': len(cases),",
                "    'mean_score': 1.0,",
                "    'duration_sec': 0.01 * len(cases),",
                "}",
                "result_path.write_text(json.dumps({'summary': summary, 'cases': cases}), encoding='utf-8')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    config = ExperimentConfig(
        name="script-runner-pythonpath",
        workspace_root=workspace,
        output_root=tmp_path / "runs",
        max_iterations=1,
        proposer=ProposerConfig(backend="manual", manual_source_dir=tmp_path / "unused"),
        runner=RunnerConfig(
            kind="script",
            project_root=workspace,
            script=ScriptRunnerConfig(
                command=[sys.executable, str(script_path)],
                result_json_path="result.json",
            ),
        ),
        policy=PolicyConfig(),
        validation=ValidationConfig(
            kind="script",
            script=[sys.executable, str(Path("tests/fixtures/validate_ok.py").resolve())],
        ),
        surfaces={
            "agent_entry": WorkspaceFileSurfaceConfig(
                name="agent_entry",
                kind="workspace_file",
                target="agent.py",
                filename="agent.py",
                base_file=workspace / "agent.py",
            )
        },
        cases=[
            CaseConfig(
                id="train.tau_case",
                split="train",
                runner_ref="tau2.airline.task.0",
                metadata={"task_id": "0"},
            )
        ],
        context=ContextConfig(),
        reporting=ReportingConfig(),
        config_path=tmp_path / "inline.toml",
    )

    result = run_baseline(config)

    assert result.validation.ok is True
    assert result.train is not None
    assert result.train.summary.n_passed == 1
