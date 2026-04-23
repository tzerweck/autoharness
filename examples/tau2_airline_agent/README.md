# tau2 Airline Agent Example

This example scaffolds the first real benchmark-backed AutoHarness experiment against the `airline` domain in `tau2-bench`.

What is included:

- a benchmark-backed airline harness with two runtime modes:
  - `plain`
  - `ace_static`
- editable prompt/controller surfaces for harness optimization
- a runtime-registered tau2 custom agent that consumes those harness files
- an AutoHarness `script` runner wrapper that evaluates fixed tau2 task IDs
- curated train / holdout / scorecard task manifests

The wrapper already does the benchmark-side work that we can lock down now:

- resolves an external tau2 checkout
- runs fixed task IDs through a programmatic tau2 worker
- records per-case results into the AutoHarness result schema
- saves raw benchmark artifacts for debugging

Before treating benchmark gains as meaningful harness gains, you still need:

- real model credentials
- first baseline runs in both `plain` and `ace_static`

## Expected external checkout

Keep `tau2-bench` outside this repository, for example:

```text
../tau2-bench
```

or:

```text
examples/tau2_airline_agent/external/tau2-bench
```

You can also point AutoHarness at any checkout with:

```bash
export AUTOHARNESS_TAU2_ROOT=/absolute/path/to/tau2-bench
```

## Required environment

Set the benchmark models outside the config so you can swap them without editing tracked files:

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

The bundled experiment configs already default all four model roles to
`{"temperature": 0.0}` for reproducibility. Override those env vars only if you
explicitly want a higher-variance run.

## First-pass workflow

1. Clone and install `tau2-bench`.
2. Review the current fixed task splits in `eval/*.txt` and adjust them if you want a different first-pass subset.
3. Run the plain baseline:
   `autoharness baseline --config examples/tau2_airline_agent/experiment_plain.toml`
4. Run the ACE-static baseline:
   `autoharness baseline --config examples/tau2_airline_agent/experiment.toml`
5. Inspect the saved raw tau2 outputs and ACE artifacts under the candidate eval directory.

Current split sizes:

- `train`: 10 tasks
- `holdout`: 5 tasks
- `scorecard`: 5 tasks
