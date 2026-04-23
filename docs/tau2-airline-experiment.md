# tau2 Airline Experiment

This document describes the first real benchmark-backed AutoHarness experiment in this repository.

## Goal

Use AutoHarness to improve an airline support harness against the `airline` domain in `tau2-bench`, while keeping:

- the benchmark fixed
- the model provider fixed
- the task splits fixed

The editable surface stays on the harness side:

- `controller.py`
- `system_prompt.md`
- `policy_prompt.md`
- `tool_instructions.md`
- `skillbook_template.md`
- `reflector_prompt.md`
- `skill_manager_prompt.md`

## Current Repository State

Implemented:

- example workspace at `examples/tau2_airline_agent/`
- `plain` baseline config at `examples/tau2_airline_agent/experiment_plain.toml`
- `ace_static` config at `examples/tau2_airline_agent/experiment.toml`
- fixed-task script-runner adapter at `examples/tau2_airline_agent/eval/run_tau2_split.py`
- tau2 helper module at `autoharness/integrations/tau2.py`
- tau2 worker module at `autoharness/integrations/tau2_worker.py`
- example-side ACE runtime modules under `examples/tau2_airline_agent/ace/`
- curated train / holdout / scorecard task manifests
- config that validates with the current AutoHarness loader
- runtime custom-agent registration so tau2 executes an AutoHarness-built agent from the editable harness bundle
- local import/task-loading verification against the sibling checkout at `../tau2-bench`

Verified locally:

- AutoHarness finds the local tau2 checkout at `/scratch/tzerweck/other/Kayba/tau2-bench`
- the tau2 import path works through the same `uv`-based execution path the worker uses
- airline task loading works through `get_tasks("airline", task_ids=["1"])`

What is still not done:

- running a full airline baseline with real model credentials
- comparing `plain` vs `ace_static` baselines on those curated splits

## External Checkout

Keep `tau2-bench` outside this repository.

Recommended layouts:

```text
../tau2-bench
```

or:

```text
examples/tau2_airline_agent/external/tau2-bench
```

You can also override detection with:

```bash
export AUTOHARNESS_TAU2_ROOT=/absolute/path/to/tau2-bench
```

If you want to force a specific tau2 interpreter instead of the default `uv run` path:

```bash
export AUTOHARNESS_TAU2_PYTHON=/absolute/path/to/python
```

## Model Configuration

The example intentionally leaves model IDs outside tracked files.

Set:

```bash
export AUTOHARNESS_TAU2_AGENT_MODEL="gpt-4.1-mini-2025-04-14"
export AUTOHARNESS_TAU2_USER_MODEL="gpt-4.1-2025-04-14"
export AUTOHARNESS_TAU2_REFLECTOR_MODEL="gpt-4.1-mini-2025-04-14"
export AUTOHARNESS_TAU2_SKILL_MANAGER_MODEL="gpt-4.1-mini-2025-04-14"
```

Optional:

```bash
export AUTOHARNESS_TAU2_USER_BACKEND="user_simulator"
```

The example configs now pin all four model roles to `{"temperature": 0.0}` in
`[runner.env]` so the first benchmarked comparisons are less noisy. Only
override those env vars if you intentionally want stochastic runs.

By default the adapter executes tau2 through:

```bash
uv run --directory <tau2-root> --extra knowledge --with scipy --with websockets python
```

The worker also installs lightweight text-mode shims for voice-only imports like `pyaudio` and `elevenlabs`, because the current tau2 package import path reaches optional voice modules even for text benchmarks.

## Runtime Modes

`plain`
- no retrieved skill block
- no post-episode reflection
- no skill-store updates

`ace_static`
- retrieve a fixed skill snapshot once at episode start
- inject that skill block into the TAU agent context for the whole episode
- after each `train` episode, run Reflector then SkillManager
- write a train-only evolving skill store
- use a frozen read-only train snapshot for `holdout` and `scorecard`

## Fixed Splits

The example now ships with a first-pass curated split:

- `train`: `0, 3, 4, 10, 12, 20, 27, 33, 40, 46`
- `holdout`: `2, 8, 13, 18, 24`
- `scorecard`: `6, 16, 19, 26, 44`

Files:

- `examples/tau2_airline_agent/eval/train_task_ids.txt`
- `examples/tau2_airline_agent/eval/holdout_task_ids.txt`
- `examples/tau2_airline_agent/eval/scorecard_task_ids.txt`

These are intentionally small enough for the first benchmarked baselines. If they prove too noisy or too narrow, the next refinement is to expand the train set and rerank the holdout/scorecard mixture, not to randomize tasks between runs.

## First Local Workflow

```bash
.venv/bin/python -m autoharness.cli validate-config examples/tau2_airline_agent/experiment.toml
.venv/bin/python -m autoharness.cli validate-config examples/tau2_airline_agent/experiment_plain.toml
```

After the external benchmark checkout and environment variables are ready:

```bash
.venv/bin/python -m autoharness.cli baseline --config examples/tau2_airline_agent/experiment_plain.toml
.venv/bin/python -m autoharness.cli baseline --config examples/tau2_airline_agent/experiment.toml
```

The adapter writes:

- the harness bundle snapshot
- tau2 worker command artifacts
- raw worker stdout / stderr
- worker summaries
- raw tau2 `results.json` files
- ACE per-case artifacts like:
  - retrieved skill context
  - reflection output
  - skill-manager output
  - evolving train snapshot

## Honest Status

The architecture gap is closed. The remaining work is benchmark setup work:

1. set the real model credentials for:
   - user simulator
   - TAU agent
   - reflector
   - skill manager
2. run the `plain` baseline
3. run the `ace_static` baseline
4. confirm benchmark scores move when harness surfaces change

Only after that should holdout gains be treated as true AutoHarness improvements on tau2 airline.
