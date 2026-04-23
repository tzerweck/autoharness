# AutoHarness Engineering

This repository is building an agent-harness-first framework for improving agent scaffolds through iterative evaluation.

Current status:

- research synthesis is in `docs/`
- the implementation plan is in `docs/agent-harness-v1-implementation-plan.md`
- the initial Python package skeleton lives in `autoharness/`
- a demonstrative example harness lives in `examples/simple_pytest_agent/`
- a first benchmark-backed tau2 airline integration lives in `examples/tau2_airline_agent/`

Today the repository includes:

- a working `autoharness validate-config` CLI path
- a Pydantic-based experiment config loader
- baseline and iterative run orchestration
- validation through `python_import` and `script` modes
- runner support for `pytest` and `script`
- per-case and batch `pytest` execution modes
- proposer support for `command` and `manual`
- periodic holdout-aware promotion logic
- run-state persistence and resume support
- reporting and inspection commands
- ranked frontier visibility for promoted and `screened_in` candidates
- richer proposer context bundles backed by frontier history
- candidate surface snapshots and diffs
- a demonstrative example harness plus integration tests
- a tau2 airline benchmark adapter with runtime custom-agent registration

Planned next:

- Harbor runner integration
- multi-candidate search beyond a single proposal per iteration
- deeper structured proposer contracts
- curated real tau2 task manifests plus the first real airline baseline run
- performance tuning for very large eval suites

Typical local workflow:

```bash
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python -m autoharness.cli validate-config examples/simple_pytest_agent/experiment.toml
.venv/bin/python -m autoharness.cli baseline --config examples/simple_pytest_agent/experiment.toml
.venv/bin/python -m autoharness.cli validate-config examples/tau2_airline_agent/experiment.toml
.venv/bin/python -m autoharness.cli validate-config examples/tau2_airline_agent/experiment_plain.toml
.venv/bin/python -m autoharness.cli run --config examples/simple_pytest_agent/experiment.toml --iterations 1
.venv/bin/pytest -q
```

For the first benchmark-backed experiment, see [docs/tau2-airline-experiment.md](/scratch/tzerweck/other/Kayba/autoharnessengineering/docs/tau2-airline-experiment.md).
