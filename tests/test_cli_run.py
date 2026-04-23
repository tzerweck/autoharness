from __future__ import annotations

import sys
from pathlib import Path

from autoharness.cli import main


def test_cli_run_executes_end_to_end(tmp_path: Path) -> None:
    workspace_root = Path("examples/simple_pytest_agent").resolve()
    output_root = tmp_path / "runs"
    proposer_script = Path("tests/fixtures/improve_tools.py").resolve()
    config_path = tmp_path / "experiment.toml"
    config_path.write_text(
        f"""
[experiment]
name = "cli-run-example"
workspace_root = "{workspace_root}"
output_root = "{output_root}"
stack = "python"
max_iterations = 1

[proposer]
backend = "command"
command = ["{sys.executable}", "{proposer_script}"]

[runner]
kind = "pytest"
project_root = "."

[runner.pytest]
pytest_args = ["-q"]

[policy]
primary_metric = "pass_rate"
holdout_every = 1
require_holdout_for_promotion = true

[validation]
kind = "python_import"
entrypoint = "agent:build_agent"

[surfaces.agent_entry]
kind = "workspace_file"
target = "agent.py"
filename = "agent.py"
base_file = "agent.py"

[surfaces.prompt]
kind = "workspace_file"
target = "prompt.md"
filename = "prompt.md"
base_file = "prompt.md"

[surfaces.tools]
kind = "workspace_file"
target = "tools.py"
filename = "tools.py"
base_file = "tools.py"

[[cases]]
id = "train.math_tool"
runner_ref = "tests/evals/test_agent.py::test_choose_math_tool"
split = "train"

[[cases]]
id = "train.solve_math"
runner_ref = "tests/evals/test_agent.py::test_solve_math_task"
split = "train"

[[cases]]
id = "train.solve_multiply"
runner_ref = "tests/evals/test_agent.py::test_solve_multiply_task"
split = "train"

[[cases]]
id = "holdout.solve_search"
runner_ref = "tests/evals/test_agent.py::test_solve_search_task"
split = "holdout"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    exit_code = main(["run", "--config", str(config_path), "--iterations", "1"])

    assert exit_code == 0
    run_dirs = list(output_root.glob("cli-run-example_*"))
    assert len(run_dirs) == 1
    frontier = (run_dirs[0] / "frontier.json").read_text(encoding="utf-8")
    assert "iter_001_cand_a" in frontier

    assert main(["report", "--run-dir", str(run_dirs[0])]) == 0
    assert main(["inspect", "--run-dir", str(run_dirs[0])]) == 0
    assert (run_dirs[0] / "reports" / "summary.md").exists()
    assert (run_dirs[0] / "reports" / "final.md").exists()
    summary_text = (run_dirs[0] / "reports" / "summary.md").read_text(encoding="utf-8")
    assert "## Frontier" in summary_text


def test_cli_run_can_resume_existing_run(tmp_path: Path) -> None:
    workspace_root = Path("examples/simple_pytest_agent").resolve()
    output_root = tmp_path / "runs"
    proposer_script = Path("tests/fixtures/improve_tools.py").resolve()
    config_path = tmp_path / "resume-experiment.toml"
    config_path.write_text(
        f"""
[experiment]
name = "resume-example"
workspace_root = "{workspace_root}"
output_root = "{output_root}"
stack = "python"
max_iterations = 0

[proposer]
backend = "command"
command = ["{sys.executable}", "{proposer_script}"]

[runner]
kind = "pytest"
project_root = "."

[runner.pytest]
pytest_args = ["-q"]

[policy]
primary_metric = "pass_rate"
holdout_every = 1
require_holdout_for_promotion = true

[validation]
kind = "python_import"
entrypoint = "agent:build_agent"

[surfaces.agent_entry]
kind = "workspace_file"
target = "agent.py"
filename = "agent.py"
base_file = "agent.py"

[surfaces.prompt]
kind = "workspace_file"
target = "prompt.md"
filename = "prompt.md"
base_file = "prompt.md"

[surfaces.tools]
kind = "workspace_file"
target = "tools.py"
filename = "tools.py"
base_file = "tools.py"

[[cases]]
id = "train.math_tool"
runner_ref = "tests/evals/test_agent.py::test_choose_math_tool"
split = "train"

[[cases]]
id = "train.solve_math"
runner_ref = "tests/evals/test_agent.py::test_solve_math_task"
split = "train"

[[cases]]
id = "train.solve_multiply"
runner_ref = "tests/evals/test_agent.py::test_solve_multiply_task"
split = "train"

[[cases]]
id = "holdout.solve_search"
runner_ref = "tests/evals/test_agent.py::test_solve_search_task"
split = "holdout"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert main(["run", "--config", str(config_path)]) == 0
    run_dirs = list(output_root.glob("resume-example_*"))
    assert len(run_dirs) == 1
    state_before = (run_dirs[0] / "state.json").read_text(encoding="utf-8")
    assert '"last_completed_iteration": 0' in state_before

    assert main(["run", "--config", str(config_path), "--resume", "--iterations", "1"]) == 0
    state_after = (run_dirs[0] / "state.json").read_text(encoding="utf-8")
    assert '"last_completed_iteration": 1' in state_after
    assert '"champion_candidate_id": "iter_001_cand_a"' in state_after


def test_cli_run_resumes_from_interrupted_iteration(tmp_path: Path) -> None:
    workspace_root = Path("examples/simple_pytest_agent").resolve()
    output_root = tmp_path / "runs"
    proposer_script = Path("tests/fixtures/improve_tools.py").resolve()
    config_path = tmp_path / "interrupt-experiment.toml"
    config_path.write_text(
        f"""
[experiment]
name = "interrupt-example"
workspace_root = "{workspace_root}"
output_root = "{output_root}"
stack = "python"
max_iterations = 0

[proposer]
backend = "command"
command = ["{sys.executable}", "{proposer_script}"]

[runner]
kind = "pytest"
project_root = "."

[runner.pytest]
pytest_args = ["-q"]

[policy]
primary_metric = "pass_rate"
holdout_every = 1
require_holdout_for_promotion = true

[validation]
kind = "python_import"
entrypoint = "agent:build_agent"

[surfaces.agent_entry]
kind = "workspace_file"
target = "agent.py"
filename = "agent.py"
base_file = "agent.py"

[surfaces.prompt]
kind = "workspace_file"
target = "prompt.md"
filename = "prompt.md"
base_file = "prompt.md"

[surfaces.tools]
kind = "workspace_file"
target = "tools.py"
filename = "tools.py"
base_file = "tools.py"

[[cases]]
id = "train.math_tool"
runner_ref = "tests/evals/test_agent.py::test_choose_math_tool"
split = "train"

[[cases]]
id = "train.solve_math"
runner_ref = "tests/evals/test_agent.py::test_solve_math_task"
split = "train"

[[cases]]
id = "train.solve_multiply"
runner_ref = "tests/evals/test_agent.py::test_solve_multiply_task"
split = "train"

[[cases]]
id = "holdout.solve_search"
runner_ref = "tests/evals/test_agent.py::test_solve_search_task"
split = "holdout"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    assert main(["run", "--config", str(config_path)]) == 0
    run_dirs = list(output_root.glob("interrupt-example_*"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]
    state_path = run_dir / "state.json"
    state = state_path.read_text(encoding="utf-8")
    assert '"last_completed_iteration": 0' in state

    partial_candidate = run_dir / "candidates" / "iter_001_cand_a"
    partial_candidate.mkdir(parents=True)
    (partial_candidate / "junk.txt").write_text("partial", encoding="utf-8")
    state_path.write_text(
        state.replace('"active_iteration_index": null', '"active_iteration_index": 1').replace(
            '"active_candidate_id": null', '"active_candidate_id": "iter_001_cand_a"'
        ),
        encoding="utf-8",
    )

    assert main(["run", "--config", str(config_path), "--resume", "--iterations", "1"]) == 0
    assert not (partial_candidate / "junk.txt").exists()
    state_after = state_path.read_text(encoding="utf-8")
    assert '"last_completed_iteration": 1' in state_after
