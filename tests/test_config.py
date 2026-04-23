from pathlib import Path

from autoharness.config import load_experiment_config


def test_load_example_config() -> None:
    config = load_experiment_config(
        Path("examples/simple_pytest_agent/experiment.toml")
    )
    assert config.name == "simple-pytest-agent"
    assert config.proposer.backend == "command"
    assert sorted(config.surfaces) == ["agent_entry", "prompt", "tools"]
    assert sum(1 for case in config.cases if case.split == "train") == 3
