from pathlib import Path

from autoharness.config import load_experiment_config


def test_load_ace_tau_real_config_includes_second_wave_surfaces() -> None:
    config = load_experiment_config(Path("examples/ace_tau_real/experiment.toml"))

    assert config.name == "ace-tau-real-airline"
    assert config.workspace_root.name == "agentic-context-engine-22-04"
    assert sorted(config.surfaces) == ["ace_code"]
    surface = config.surfaces["ace_code"]
    assert surface.kind == "workspace_tree"
    assert surface.target == "ace"
    assert sum(1 for case in config.cases if case.split == "train") == 10
    assert sum(1 for case in config.cases if case.split == "holdout") == 5
    assert sum(1 for case in config.cases if case.split == "scorecard") == 5


def test_load_ace_tau_real_plain_config_uses_plain_mode() -> None:
    config = load_experiment_config(Path("examples/ace_tau_real/experiment_plain.toml"))

    assert config.name == "ace-tau-real-airline-plain"
    assert config.runner.env["AUTOHARNESS_ACE_MODE"] == "plain"
    assert sorted(config.surfaces) == ["ace_code"]
