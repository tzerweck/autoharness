# Agent Harness Evolution Framework: V1 Implementation Plan

Status: Draft  
Date: April 20, 2026

## Objective

Build the first working version of an open-source framework that automatically improves **agent harnesses** by iteratively:

1. proposing harness edits
2. validating candidate harnesses
3. evaluating them on train cases
4. selectively promoting them with holdout evaluation
5. storing all relevant code, traces, and outcomes in a filesystem-native history

This document turns the v1 proposal into an implementation plan with:

- module boundaries
- schemas
- CLI shape
- milestone order
- testing strategy
- open implementation decisions

## Recommended Implementation Bias

The framework should be implemented as a **Python 3.11+ package** with:

- a **small dependency surface**
- a **CLI-first workflow**
- **TOML** experiment configs
- **Pydantic v2** for schemas and validation
- a **filesystem-backed store**, not a database
- **adapter interfaces** for proposers, runners, and surfaces

This keeps the MVP simple, inspectable, and aligned with the underlying research.

## Scope Of The MVP

### MVP Must Include

- experiment config loading and validation
- declared editable surfaces
- candidate workspace materialization
- validation stage
- `pytest` runner
- train / holdout split handling
- keep / discard / promote policy
- filesystem-native run history
- markdown and JSON reporting
- one proposer backend that can run end-to-end
- one starter example agent harness

### MVP Should Include If Affordable

- generic `script` runner
- command-based proposer backend
- proposer context builder with top-k candidate selection
- patch diff generation

### MVP Should Not Include

- Harbor adapter if it slows the first end-to-end path
- UI
- distributed scheduling
- multi-agent proposer swarms
- benchmark auto-generation
- deep governance / constitution systems

## Assumptions

These assumptions are recommended unless we decide otherwise:

1. The target repository is Python-first in v1.
2. The first benchmark path is `pytest`.
3. The first public example is a coding/terminal-style agent.
4. Candidate artifacts are stored as full surface snapshots plus diffs.
5. Holdout detailed artifacts are not exposed to the proposer.
6. The proposer works in an isolated workspace copy, not directly in the target workspace.

## Resolved Defaults

The following implementation defaults are now locked in:

1. The MVP includes an automated **`command` proposer**.
2. The first bundled example is a **lightweight coding/terminal-style agent**.
3. The starter template exposes **`agent.py` + `prompt.md` + `tools.py`**.
4. The bundled eval suite is **demonstrative**, serving as a development target and usage example rather than a benchmark-grade suite.

## High-Level Architecture

The framework should have six core subsystems:

1. `config`
   - experiment schema
   - case schema
   - policy schema
   - loader and normalization

2. `surfaces`
   - editable surface definitions
   - materialization and patching logic

3. `runner`
   - validation execution
   - train / holdout / scorecard execution
   - result normalization

4. `proposer`
   - proposer backends
   - workspace setup
   - result capture

5. `store`
   - canonical run layout
   - candidate persistence
   - summaries and frontier

6. `selection`
   - screening
   - promotion
   - champion / frontier updates

Two supporting subsystems should be first-class:

7. `context`
   - proposer-visible history selection
   - train-only artifact exposure

8. `reporting`
   - markdown summaries
   - final run reports

## Package Layout

Recommended initial package structure:

```text
autoharness/
  __init__.py
  cli.py
  constants.py
  errors.py
  config/
    __init__.py
    models.py
    load.py
    normalize.py
  surfaces/
    __init__.py
    base.py
    workspace_file.py
    module_attr.py
    materialize.py
    diff.py
  validation/
    __init__.py
    base.py
    python.py
  runners/
    __init__.py
    base.py
    pytest_runner.py
    script_runner.py
    result_parser.py
  proposer/
    __init__.py
    base.py
    manual.py
    command.py
    session.py
  context/
    __init__.py
    builder.py
    manifest.py
  selection/
    __init__.py
    policy.py
    scoring.py
  store/
    __init__.py
    layout.py
    writer.py
    query.py
    ledger.py
  reporting/
    __init__.py
    summary.py
    final_report.py
  orchestration/
    __init__.py
    baseline.py
    iterate.py
    finalize.py
  examples/
    simple_pytest_agent/
  templates/
    simple_agent/
```

## Core Schemas

## 1. ExperimentConfig

This is the top-level config model.

Recommended fields:

- `name: str`
- `workspace_root: Path`
- `output_root: Path | None`
- `stack: Literal["python"]`
- `max_iterations: int`
- `proposer: ProposerConfig`
- `runner: RunnerConfig`
- `policy: PolicyConfig`
- `validation: ValidationConfig`
- `surfaces: dict[str, SurfaceConfig]`
- `cases: list[CaseConfig]`
- `context: ContextConfig`
- `reporting: ReportingConfig`

Notes:

- `output_root` should default to `<cwd>/runs`
- `stack` can stay narrow in v1
- config normalization should resolve all relative paths against the config file directory

## 2. SurfaceConfig

Recommended shared fields:

- `name: str`
- `kind: Literal["workspace_file", "module_attr"]`
- `target: str`
- `description: str | None`
- `read_only: bool = False`

### `workspace_file`

- `filename: str`
- `base_file: str`

### `module_attr`

- `module: str`
- `attribute: str`
- `base_value: str`
- `emit_file: str`

Rationale:

- `emit_file` lets us render module-attribute values into files in the proposer workspace, then map them back into runtime patching cleanly

## 3. CaseConfig

Recommended fields:

- `id: str`
- `split: Literal["train", "holdout", "scorecard"]`
- `runner_ref: str`
- `stratum: str | None`
- `weight: float = 1.0`
- `tags: list[str] = []`
- `timeout_sec: float | None`
- `metadata: dict[str, Any] = {}`

Key design choice:

Use `id` as the framework identifier and `runner_ref` as the runner-specific selector. This prevents `case_id` from being overloaded.

## 4. PolicyConfig

Recommended fields:

- `primary_metric: Literal["pass_rate", "mean_score"]`
- `secondary_metrics: list[str] = []`
- `screen_split: Literal["train"] = "train"`
- `holdout_every: int = 3`
- `require_holdout_for_promotion: bool = True`
- `min_primary_improvement: float = 0.0`
- `allow_tie_if_secondary_improves: bool = True`
- `prefer_simpler_on_tie: bool = True`
- `max_allowed_holdout_regression: float = 0.0`
- `keep_top_k_visible_candidates: int = 20`

V1 recommendation:

- one active champion
- train-screened candidates may remain visible in history even if not promoted
- only promoted candidates can replace the champion

## 5. ValidationConfig

Recommended fields:

- `kind: Literal["python_import", "script"]`
- `entrypoint: str | None`
- `script: str | None`
- `timeout_sec: float = 30.0`

V1 default:

- `python_import` validation for Python agents

## 6. ProposerConfig

Recommended fields:

- `backend: Literal["manual", "command"]`
- `max_turns: int = 50`
- `timeout_sec: float | None`
- `command: list[str] | None`
- `environment: dict[str, str] = {}`
- `allowed_tools: list[str] = []`
- `system_prompt_file: str | None`

Important choice:

The first production-grade backend should be **`command`**, not a provider-specific API backend. That gives us:

- lower coupling
- easier local experimentation
- easier support for different coding agents

The first fully automated backend can simply execute a configured command in the proposer workspace and expect file edits plus a metadata output contract.

## 7. RunnerConfig

Recommended fields:

- `kind: Literal["pytest", "script"]`
- `project_root: Path | None`
- `env: dict[str, str] = {}`
- `pytest: PytestRunnerConfig | None`
- `script: ScriptRunnerConfig | None`

### PytestRunnerConfig

- `pytest_args: list[str] = []`
- `artifact_dir_env: str = "AUTOHARNESS_ARTIFACT_DIR"`
- `candidate_dir_env: str = "AUTOHARNESS_CANDIDATE_DIR"`
- `report_json_path: str = ".autoharness_pytest_report.json"`
- `junit_xml_path: str | None = None`

### ScriptRunnerConfig

- `command: list[str]`
- `result_json_path: str`

## 8. ContextConfig

Recommended fields:

- `history_strategy: Literal["recent_plus_best"] = "recent_plus_best"`
- `max_candidates: int = 8`
- `max_failed_cases_per_candidate: int = 5`
- `include_diffs: bool = True`
- `include_train_traces: bool = True`
- `include_holdout_details: bool = False`
- `emit_manifest: bool = True`

This config controls what the proposer can see.

## 9. Result Schemas

Implement these schemas early:

- `ValidationResult`
- `CaseResult`
- `SplitSummary`
- `CandidateMeta`
- `CandidateDecision`
- `ProposerResult`
- `FrontierState`
- `LedgerEvent`

These should be Pydantic models and persisted as JSON / JSONL.

## Candidate State Machine

Explicit candidate states will make orchestration simpler.

Recommended states:

- `draft`
- `materialized`
- `validation_failed`
- `validated`
- `train_failed`
- `train_evaluated`
- `screened_in`
- `screened_out`
- `holdout_evaluated`
- `promoted`
- `discarded`
- `final_selected`

This should be represented in `CandidateMeta` plus append-only `ledger.jsonl` events.

## Proposer Design

## Why `manual` And `command` Should Exist First

We need a testable and generic path before binding to any one vendor.

### `manual` backend

Purpose:

- testing the framework end-to-end
- allowing humans to propose candidate edits manually
- creating deterministic integration tests

Contract:

- reads a candidate surface directory prepared by the user
- emits `ProposerResult` with zero tool usage

### `command` backend

Purpose:

- support Codex, Claude Code, Aider, or custom shell-driven agents
- stay provider-agnostic

Contract:

- framework creates proposer workspace
- framework writes `context/` bundle and editable surfaces
- framework executes configured command in that workspace
- backend expects modified surfaces plus a metadata file such as `proposer_result.json`

Recommended proposer workspace structure:

```text
proposer_workspace/
  editable/
    agent.py
    prompt.md
    tools.py
  context/
    experiment_summary.md
    frontier.json
    prior_candidates/
    failure_examples/
    manifest.json
  contract/
    instructions.md
    writable_surfaces.json
    proposer_result.schema.json
```

This is where the filesystem-native Meta-Harness idea should live in a disciplined way.

## Why A Context Builder Is Required

We should not dump the full run directory into the proposer workspace.

Reasons:

- too much noise
- harder to keep prompt-equivalent context bounded
- harder to prevent holdout leakage

Instead, the framework should implement a `ContextBuilder` that selects:

- current champion
- last `K` candidates
- best `K` candidates by train score
- top failed strata on train
- a bounded number of representative train traces

### V1 Selection Heuristic

Recommended default:

- current champion
- 3 most recent discarded candidates
- 3 strongest train-positive candidates
- up to 2 representative failures per stratum

This heuristic is good enough for the MVP and can be improved later.

## Surface Materialization

The surface layer needs to do three jobs:

1. prepare proposer-editable files
2. build candidate workspaces for evaluation
3. persist candidate surface snapshots and diffs

### `workspace_file` implementation

- copy base file into proposer workspace
- after proposer run, copy edited file into candidate workspace
- persist final file into `surfaces/`

### `module_attr` implementation

- render base value into a stable file in proposer workspace
- after proposer run, read file contents
- patch runtime module attribute during candidate workspace materialization
- persist emitted file plus patch metadata

V1 simplification:

Even for `module_attr`, we should store an emitted file in the candidate snapshot. This makes history inspection easier.

## Validation Plan

Validation should be a first-class subsystem, not just an ad hoc pre-step.

### V1 validator types

1. `python_import`
   - import candidate entrypoint
   - instantiate or load configured symbol
   - verify basic contract

2. `script`
   - run configurable command
   - check exit code

### `python_import` default contract

The template should define a standard entrypoint such as:

```python
def build_agent() -> Any:
    ...
```

The validator can then:

- add candidate workspace to `PYTHONPATH`
- import module
- call `build_agent`
- verify non-null result

This is intentionally minimal.

## Runner Implementation

## `pytest` Runner

The `pytest` runner should be the first-class path.

### Execution model

- materialize candidate workspace
- set candidate env vars
- run pytest with case selectors for one split
- capture process exit code
- parse machine-readable report
- normalize per-case results and aggregate summary

### Report capture options

There are two possible ways to capture result structure:

1. rely on `pytest-json-report`
2. ship our own lightweight pytest plugin

Recommendation:

Implement a lightweight **bundled pytest plugin**.

Reasons:

- better control over per-case metadata
- no dependency on third-party plugin behavior
- easier artifact integration

The plugin should capture:

- nodeid
- status
- duration
- stdout / stderr paths if preserved
- artifact paths if tests emit them through a helper

### Artifact helper

Add a small helper module for tests:

```python
from autoharness.testing import register_artifact
```

This lets eval tests report:

- trace JSON files
- screenshots
- logs
- verifier outputs

V1 fallback:

artifact paths are optional

## `script` Runner

This should exist in MVP if the cost is reasonable.

Execution model:

- run configured command in candidate workspace
- expect a JSON result file at a declared path
- normalize into `CaseResult` and `SplitSummary`

This is the escape hatch for benchmarks that are not pytest-native.

## Selection Policy Implementation

Selection should be deterministic and auditable.

### V1 algorithm

For each candidate:

1. run validation
2. if validation fails: discard
3. run train
4. compare train summary against current champion
5. if train does not clear screening thresholds: discard
6. if this iteration requires holdout:
   - run holdout
   - compare against champion holdout
   - promote or discard
7. otherwise:
   - mark as `screened_in`
   - keep visible but not champion-eligible

### Champion rules

- baseline becomes initial champion after baseline train + holdout
- only promoted candidates can replace champion
- champion replacement writes a frontier update event

### Tie-breakers

When configured metrics are within threshold:

prefer, in order:

1. lower holdout cost
2. lower average latency
3. fewer changed surfaces
4. smaller diff footprint

This gives the system a slight bias toward simpler harnesses.

## Store Layout Implementation

## Top-level layout

```text
runs/<experiment_name>_<timestamp>/
  experiment.json
  frontier.json
  ledger.jsonl
  reports/
  proposer_sessions/
  candidates/
  context_cache/
```

### Candidate layout

```text
candidates/iter_003_cand_a/
  meta.json
  hypothesis.md
  surfaces/
  diffs/
  validation/
  eval/
    train/
    holdout/
    scorecard/
  proposer/
  decision.json
```

### Privacy boundary for proposer context

To reduce holdout leakage:

- full candidate store contains everything
- proposer workspace receives a **filtered** context bundle
- filtered bundle includes:
  - train details
  - aggregate holdout summaries only
  - no holdout case-level failures

This is an important implementation detail and should not be deferred.

## Ledger Design

Use append-only `ledger.jsonl`.

Each event should contain:

- timestamp
- iteration
- candidate_id
- event_type
- state
- key metrics
- champion_id if relevant

Example event types:

- `baseline_created`
- `validation_completed`
- `train_completed`
- `holdout_completed`
- `candidate_discarded`
- `candidate_promoted`
- `frontier_updated`
- `run_finalized`

This gives us a durable audit trail without introducing a database.

## Reporting Plan

The framework should generate three report forms:

1. machine-readable JSON
2. append-only JSONL ledger
3. markdown summaries for humans

### Baseline summary

Must include:

- baseline validation status
- train metrics
- holdout metrics
- cost summary
- case counts by stratum

### Iteration summary

For each iteration:

- candidate hypothesis
- surfaces changed
- validation outcome
- train outcome
- holdout outcome if run
- decision
- champion delta

### Final summary

Must include:

- baseline vs final comparison
- top promoted candidates
- discarded candidate counts by reason
- dominant failure strata
- total search cost and duration

## CLI Plan

The CLI should be intentionally small in v1.

Recommended commands:

### `autoharness validate-config`

Purpose:

- parse config
- resolve paths
- validate schema

### `autoharness baseline`

Purpose:

- materialize baseline
- run validation
- run baseline train and holdout
- write initial store

### `autoharness run`

Purpose:

- run full optimization loop

Flags:

- `--config`
- `--iterations`
- `--resume`
- `--dry-run`

### `autoharness report`

Purpose:

- generate or regenerate markdown summaries

### `autoharness inspect`

Purpose:

- show frontier
- show top candidates
- optionally dump candidate metrics

V1 note:

Do not overbuild the CLI before the core orchestration is stable.

## Orchestration Flow

## Phase 1: Config And Initialization

1. load TOML config
2. validate schema
3. normalize paths
4. initialize run directory
5. write normalized `experiment.json`

## Phase 2: Baseline

1. load base surfaces from workspace
2. materialize baseline candidate
3. run validation
4. run train
5. run holdout
6. update frontier
7. write baseline reports

## Phase 3: Iterative Search

For each iteration:

1. build proposer context bundle
2. create proposer workspace
3. run proposer backend
4. extract edited surfaces
5. materialize candidate workspace
6. write candidate snapshots and diff
7. run validation
8. if validation fails, record and continue
9. run train
10. apply train screening
11. if holdout required, run holdout
12. apply promotion policy
13. update frontier and reports

## Phase 4: Finalization

1. select final promoted candidate
2. optionally run scorecard
3. write final report

## Testing Strategy

Testing needs to be planned early because orchestration code becomes brittle quickly.

## Unit Tests

Must cover:

- config loading and path normalization
- surface materialization
- module-attribute rendering
- diff generation
- policy decisions
- context bundle filtering
- ledger event writing

## Integration Tests

Must cover:

1. baseline run with `manual` proposer
2. one successful iteration with `manual` proposer
3. validation failure path
4. train-screened-but-not-promoted path
5. promoted candidate replaces champion
6. holdout details excluded from proposer context

## Golden Tests

Recommended for:

- report markdown output
- frontier JSON shape
- candidate directory layout

## Example-Based Tests

The template example should be used as a real integration test fixture.

This matters because the public example often becomes the real compatibility target.

## Example Template Plan

The first public example should be:

- Python-based
- pytest-evaluated
- small enough to run locally
- agent-like enough to show meaningful harness changes

Recommended surfaces:

- `agent.py`
- `prompt.md`
- `tools.py`

Recommended eval strata:

- tool selection
- planning
- file editing
- completion criteria

The example should include:

- a trivial baseline
- a few train tests that can be improved
- a couple of holdout cases

The goal is not a benchmark leaderboard. The goal is to demonstrate the framework end-to-end.

## Milestone Plan

## Milestone 0: Repo Skeleton

Deliverables:

- package skeleton
- `pyproject.toml`
- dependency setup
- config schema stubs
- docs placeholders

Exit criteria:

- package installs
- `autoharness --help` works

## Milestone 1: Config + Store + Baseline

Deliverables:

- TOML config loader
- normalized `ExperimentConfig`
- run directory initializer
- baseline surface capture
- ledger writer

Exit criteria:

- `validate-config` works
- baseline candidate directory is materialized correctly

## Milestone 2: Validation + Pytest Runner

Deliverables:

- `python_import` validator
- pytest runner
- bundled pytest plugin
- normalized result schemas

Exit criteria:

- baseline validation + train + holdout can run end-to-end on example project

## Milestone 3: Selection + Reporting

Deliverables:

- screening and promotion logic
- frontier updates
- markdown reporting
- inspect command

Exit criteria:

- baseline and one manual candidate can be compared and promoted correctly

## Milestone 4: Proposer Backends

Deliverables:

- `manual` backend
- `command` backend
- proposer workspace contract
- proposer result capture
- context bundle builder

Exit criteria:

- one automatic iteration can run through the command backend end-to-end

## Milestone 5: Hardening The MVP

Deliverables:

- integration tests
- leakage guardrails
- better error messages
- resume support
- final docs cleanup

Exit criteria:

- public MVP is reproducible on the example project

## Milestone 6: Post-MVP

Deferred items:

- `script` runner if not already shipped
- Harbor runner
- scorecard split support if not already complete
- richer context ranking
- repeated-trial noise handling

## Recommended Engineering Order

The first end-to-end slice should be:

1. config
2. store
3. baseline materialization
4. validator
5. pytest runner
6. selection
7. reporting
8. manual proposer
9. command proposer

This avoids building proposer complexity before evaluation is trustworthy.

## Key Tradeoffs And Recommended Answers

### 1. Provider-specific proposer vs generic command backend

Recommendation:

- ship `command` first
- add provider-native adapters later only if needed

Reason:

- avoids immediate lock-in
- lets advanced users plug in their own agent command

### 2. Database vs filesystem store

Recommendation:

- filesystem + JSON / JSONL only

Reason:

- simpler
- easier to inspect
- aligned with Meta-Harness-style history use

### 3. Full run directory visible to proposer vs filtered context bundle

Recommendation:

- filtered context bundle

Reason:

- lower noise
- better holdout hygiene
- easier future context controls

### 4. One-file-only boundary vs multiple surfaces

Recommendation:

- multiple surfaces in the framework
- one-file-like starter template for usability

### 5. Holdout every iteration vs periodic holdout

Recommendation:

- periodic holdout

Reason:

- better scientific hygiene
- lower cost

## Risks

### Risk 1: Too much framework before the first working example

Mitigation:

- keep example project in the repo from the start
- use it as the acceptance target for every milestone

### Risk 2: Proposer integration dominates the schedule

Mitigation:

- build with `manual` backend first
- keep `command` backend contract narrow

### Risk 3: Holdout leakage through filesystem access

Mitigation:

- proposer only sees generated context bundle
- do not expose full run directories directly

### Risk 4: Pytest runner cannot capture enough trace detail

Mitigation:

- support optional artifact helper
- make artifact capture best-effort in v1

## Remaining Open Questions

The directional choices are resolved. The remaining questions are now tactical:

1. How strict should the first `python_import` validator be beyond verifying `build_agent()` returns a non-null object?
2. Should the first `command` proposer contract require a structured `proposer_result.json`, or is file-diff capture enough for the first end-to-end slice?
3. How much candidate history should the first `ContextBuilder` expose by default before context size becomes noisy?

## Immediate Next Step

If you agree with the defaults, the next concrete deliverable should be a **task breakdown**:

- exact file creation list
- first schemas to implement
- first CLI commands to stub
- milestone-by-milestone issue list

That would be the bridge from planning into actual repository scaffolding.
