# Agent Harness Evolution Framework: V1 Proposal

Status: Draft  
Date: April 20, 2026

## Executive Summary

This proposal defines a first open-source release for an **agent-harness-first** framework that automatically improves agent scaffolds through iterative evaluation and code search.

The framework should:

- optimize **agent harnesses**, not arbitrary model wrappers
- support **multiple agent stacks** through adapters
- expose a **small set of editable surfaces**
- run **evaluation outside the proposer**
- preserve a **filesystem-native experience store**
- separate **train**, **holdout**, and optional **scorecard** evaluation
- default to a simple user experience while remaining extensible

This is not a clone of the official Meta-Harness repo. It is a new framework informed by:

- [Meta-Harness paper](https://arxiv.org/abs/2603.28052)
- [stanford-iris-lab/meta-harness](https://github.com/stanford-iris-lab/meta-harness)
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- [kevinrgu/autoagent](https://github.com/kevinrgu/autoagent)
- [deepagents `better-harness`](https://github.com/langchain-ai/deepagents/tree/main/examples/better-harness)
- [aiming-lab/AutoHarness](https://github.com/aiming-lab/AutoHarness)

The target identity is:

> A general framework for evolving **agent harnesses** with strong evaluation discipline, rich run history, and stack-agnostic harness adapters.

## Positioning

### What We Are Building

A framework for improving agent behavior by changing:

- system prompts and task instructions
- tool definitions and tool interfaces
- orchestration logic and turn policy
- sub-agent / handoff wiring
- verification and completion checks
- optional memory or retrieval components when they are part of the agent harness

### What We Are Not Building In V1

- a general optimizer for arbitrary non-agent model wrappers
- a full runtime governance product like AutoHarness
- a benchmark-only research artifact tied to one leaderboard
- a replacement for LangGraph, Harbor, or OpenAI Agents SDK
- a full UI product

## Design Principles

1. **Agent-harness-first**
   The framework is optimized for agent systems with tools, environment interaction, orchestration, and verifier-backed evaluation.

2. **Simple default, flexible core**
   The beginner path should feel close to `autoagent`, while the internal abstraction should support `better-harness`-style declared surfaces.

3. **Evaluator outside the proposer**
   The proposer suggests changes; a separate system validates and evaluates them.

4. **Filesystem is the source of truth**
   Prior runs must remain inspectable as raw code, scores, traces, and metadata.

5. **Explicit train/holdout discipline**
   Search should optimize on train-visible cases and use holdout carefully to avoid immediate overfitting.

6. **Editable boundary must be explicit**
   The proposer should know exactly what it may edit and what is fixed.

7. **Adapters over lock-in**
   The framework should support multiple harness stacks and evaluation stacks.

## Core V1 Decisions

### Decision 1: Build A New Framework

We should **not** make the official Meta-Harness repo the public base of this project.

We should:

- treat the official Meta-Harness code as a reference implementation
- borrow ideas and patterns aggressively
- build a clean, agent-specific framework with our own abstractions

Rationale:

- our v1 scope is narrower than Meta-Harness: agent harnesses only
- the official repo is structured like a paper release
- a new framework gives clearer long-term OSS identity

### Decision 2: Agent Harnesses Only For V1

The first release should focus on **agent harnesses**, not broader model harnesses like standalone retrieval or memory policies.

That means the core evaluation unit is an **agent task or episode**, not just a classification example or retriever call.

### Decision 3: Declared Surfaces Internally, Simple Starter Externally

The framework should support **declared editable surfaces**.

The starter experience should default to a small fixed set:

- `agent.py` or `graph.py`
- `prompt.md` or an equivalent prompt surface
- optional `tools.py`

This makes single-file mode a supported special case, not the permanent architecture.

## V1 Scope

### Primary User

A developer or researcher who already has:

- a working agent harness
- a benchmark or eval suite
- a desire to improve the harness automatically without hand-editing every iteration

### Supported Use Cases

- coding/terminal agents
- workflow agents with structured tool use
- sandboxed agents evaluated by scripts, tests, or benchmark frameworks
- agents built on LangGraph, OpenAI Agents SDK, Harbor-compatible harnesses, or custom runtimes

### Unsupported Or Deferred Use Cases

- subjective “chat quality” optimization without stable evals
- pure prompt optimization without agent behavior
- broad production governance policy engines
- multi-node distributed search orchestration

## Core Concepts

### 1. Experiment Spec

An `experiment` describes one harness optimization run.

It declares:

- workspace root
- harness stack / adapter
- proposer backend
- editable surfaces
- evaluation runner
- train / holdout / scorecard cases
- optimization policy

### 2. Surface

A `surface` is a concrete editable artifact that the inner agent actually loads during evaluation.

Examples:

- prompt text
- tool file
- tool registration file
- middleware implementation
- middleware registration or graph wiring
- orchestrator entrypoint

A surface must be one of:

- a workspace file replacement
- a module attribute patch

### 3. Candidate

A `candidate` is one proposed harness state derived from:

- a baseline or prior kept candidate
- a set of surface edits
- metadata about the proposer’s hypothesis

### 4. Case

A `case` is one evaluation target with:

- `case_id`
- `split`
- `stratum`
- optional tags / metadata

Splits:

- `train`
- `holdout`
- `scorecard`

### 5. Runner

A `runner` executes evaluation for a candidate and produces normalized results.

Supported in v1:

- `pytest`
- `harbor`
- `script`

### 6. Experience Store

The canonical directory of all prior runs, including:

- candidate code snapshots
- evaluation outputs
- traces
- summaries
- proposer logs
- keep/discard decisions

## Editable Surface Model

### Why Not One File Only

A single editable `agent.py` is attractive for simplicity, but too limiting as a general framework:

- many real harnesses split prompt, tools, and wiring
- middleware often requires both implementation and registration
- one-file systems become hard to review and reuse

### Why Not Whole-Repo Editing

Whole-repo editing is too broad for v1:

- hard to validate
- easy to leak into evaluator code or benchmark definitions
- harder for users to understand the edit boundary

### Proposed V1 Surface Model

Support these surface kinds:

1. `workspace_file`
   Replace or patch a file inside the target workspace during evaluation.

2. `module_attr`
   Patch a Python module attribute such as a prompt constant.

Each surface declares:

- `name`
- `kind`
- `target`
- `filename`
- exactly one of `base_file` or `base_value`
- optional description

### Starter Template Boundary

The starter template should expose:

- `agent_entry`
  - main orchestration / graph wiring file
- `prompt`
  - prompt file or prompt constant
- `tools`
  - optional tool file

Optional advanced surfaces:

- `middleware_impl`
- `middleware_registration`
- `skills`
- `verifier_prompt` only if that is genuinely part of the harness, not the benchmark

### Fixed Boundary

The proposer must never edit:

- runner implementation
- benchmark or case definitions
- evaluator scripts
- framework internals
- adapter boundary code designated fixed by the experiment

## Evaluation Proposal

## Evaluation Philosophy

Evaluation is **domain-dependent in implementation** but **framework-standardized in shape**.

The framework should not prescribe one benchmark system. It should prescribe one result contract.

### Standard Evaluation Splits

#### `train`

Used for frequent search-time optimization.

Purpose:

- provide dense signal every iteration
- expose visible failures to the proposer

#### `holdout`

Used periodically, not necessarily every iteration.

Purpose:

- detect train overfitting
- decide whether a candidate is worth promoting

#### `scorecard`

Optional final or checkpoint suite.

Purpose:

- broader reporting
- slower or more expensive evaluation
- benchmark-quality comparison for baseline vs final

### Recommended V1 Evaluation Policy

- run `train` every iteration
- run `holdout` only on:
  - baseline
  - promoted candidates
  - every `N` iterations, configurable
- run `scorecard` only on:
  - baseline
  - final selected candidate
  - optional milestone checkpoints

This is more disciplined than evaluating holdout every iteration.

### Candidate Lifecycle

1. proposer suggests edits
2. framework builds temporary candidate workspace
3. framework runs cheap validation
4. framework runs train eval
5. selection policy decides whether candidate merits holdout eval
6. framework optionally runs holdout
7. framework records keep/discard decision

### Cheap Validation Gate

Every candidate must pass fast validation before full eval.

Examples:

- module import
- class or function presence
- smoke task / one trivial case
- syntax check / type of object returned

This should take seconds, not minutes.

## Standard Result Contract

Every runner must normalize outputs into the same per-case schema.

### Per-case result

```json
{
  "case_id": "tests/evals/test_tool_selection.py::test_case[model]",
  "split": "train",
  "stratum": "tool_use",
  "passed": true,
  "score": 1.0,
  "duration_sec": 14.2,
  "cost_usd": 0.18,
  "n_input_tokens": 12034,
  "n_output_tokens": 2104,
  "trace_paths": ["eval/train/case_001/trajectory.json"],
  "metadata": {
    "runner_case_name": "test_tool_selection.py::test_case[model]"
  }
}
```

### Aggregate result

```json
{
  "candidate_id": "iter_003_cand_a",
  "split": "train",
  "n_cases": 24,
  "n_passed": 17,
  "pass_rate": 0.7083,
  "mean_score": 0.7417,
  "duration_sec": 642.3,
  "cost_usd": 9.84,
  "n_input_tokens": 421230,
  "n_output_tokens": 61220,
  "status": "ok"
}
```

## Runner Adapters

### 1. `pytest` Runner

Best first runner for v1.

Use when:

- the benchmark is already expressed as Python tests
- the team has custom evals
- the harness is easy to run locally

Requirements:

- configurable `project_root`
- configurable model flag or env var injection
- configurable report output path
- case IDs map naturally to test identifiers

### 2. `harbor` Runner

Important second runner because it fits agent benchmarks well.

Use when:

- tasks are containerized
- verifier outputs are already standardized
- Harbor tasks already exist

Requirements:

- path to tasks
- agent import path
- concurrency and attempt controls
- parser for per-task verifier outputs and traces

### 3. `script` Runner

Fallback adapter for custom environments.

Use when:

- the user has an existing shell-based eval harness
- the benchmark is not pytest- or Harbor-native

Requirements:

- command template
- artifact discovery rules
- parser hook or JSON contract

## Selection And Promotion Policy

### Why This Matters

We need stronger semantics than “keep if score improved.”

The framework should separate:

- **screening**
- **promotion**
- **final selection**

### Proposed V1 Policy

#### Train Screening

After train evaluation, a candidate is eligible for promotion if it satisfies at least one:

- improves primary metric by a configured margin
- matches primary metric and improves a secondary metric
- matches metrics and simplifies the harness

#### Holdout Promotion

A train-screened candidate is promoted only if holdout confirms one:

- improvement over current champion
- no regression with materially lower cost or complexity

#### Final Selection

The final selected candidate is the promoted candidate that best satisfies the configured objective:

- scalar best on primary metric
- or Pareto frontier across:
  - pass rate / score
  - cost
  - latency
  - context use

### Simplicity Rule

Borrowing from `autoresearch` and `autoagent`, simplicity should matter.

When performance is tied or nearly tied, prefer:

- fewer moving parts
- fewer surfaces changed
- less brittle logic
- lower cost

### Noise Handling

If evaluation is noisy, the policy should support:

- rerun top candidates
- require a promotion margin
- compare confidence intervals or repeated-trial averages later

Noise-aware reruns can be a v1.1 feature, but the config shape should leave room for them.

## Proposer Architecture

### Outer vs Inner Agent

The framework assumes two roles:

- **outer proposer agent**
  - reads history
  - edits allowed surfaces
  - explains hypothesis
- **inner target agent**
  - is evaluated on cases

### Proposer Constraints

The proposer should:

- see only allowed surfaces
- see visible train artifacts
- read prior candidate code, scores, and traces
- write proposed edits into a proposer workspace, not directly into the target repo

### Why Proposer Workspace Matters

Borrowing from `better-harness`, the proposer should work in an isolated temporary workspace because it:

- avoids accidental corruption of the target repo
- makes candidate materialization explicit
- simplifies diffing and rollback

### Proposer Backend Interface

V1 should define an adapter interface, even if only one backend is implemented first.

Example:

```python
class ProposerAdapter(Protocol):
    def run(self, prompt: str, workspace: Path, allowed_tools: list[str]) -> ProposerResult: ...
```

Where `ProposerResult` includes:

- messages / reasoning summary
- tool usage
- files read / written
- token usage
- structured candidate artifact if emitted

### First Backend

The first backend can be whichever coding agent is most convenient for us operationally, but the framework should not hardcode itself around that one provider.

## Experience Store Proposal

The filesystem layout should be easy for humans and proposers to query.

### Top-level structure

```text
runs/
  20260420_my-agent/
    experiment.json
    frontier.json
    ledger.jsonl
    proposer_sessions/
    candidates/
      iter_000_baseline/
      iter_001_cand_a/
      iter_001_cand_b/
```

### Candidate structure

```text
candidates/iter_001_cand_a/
  meta.json
  hypothesis.md
  surfaces/
    agent.py
    prompt.md
    tools.py
  diffs/
    unified.patch
  validation/
    result.json
    logs.txt
  eval/
    train/
      summary.json
      cases.jsonl
      traces/
    holdout/
      summary.json
      cases.jsonl
      traces/
  proposer/
    response.md
    events.jsonl
    tool_calls/
  decision.json
```

### Canonical Global Files

- `experiment.json`
  - normalized experiment config
- `frontier.json`
  - current best or Pareto frontier
- `ledger.jsonl`
  - append-only history of candidates and decisions

## Configuration Proposal

The framework should use one config file per experiment.

TOML is a good fit because `better-harness` already demonstrates a clean shape and TOML is readable for agent configs.

### Example shape

```toml
[experiment]
name = "terminal-agent-v1"
workspace_root = "/abs/path/to/agent-repo"
stack = "python"
max_iterations = 10

[proposer]
backend = "codex"
model = "gpt-5.4"
max_turns = 60

[runner]
kind = "pytest"

[runner.pytest]
project_root = "/abs/path/to/agent-repo/tests/evals"
pytest_args = ["-q"]
summary_flag = "--evals-report-file"

[policy]
primary_metric = "pass_rate"
screen_on = "train"
holdout_every = 3
require_holdout_for_keep = true
prefer_simpler_on_tie = true

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
case_id = "tests/evals/test_shell.py::test_extract_version"
split = "train"
stratum = "shell"

[[cases]]
case_id = "tests/evals/test_edit.py::test_fix_bug"
split = "train"
stratum = "editing"

[[cases]]
case_id = "tests/evals/test_planning.py::test_multistep_refactor"
split = "holdout"
stratum = "planning"

[[cases]]
case_id = "tests/evals/test_realistic.py::test_large_task"
split = "scorecard"
stratum = "realistic"
```

## Repo Shape Proposal

The public repo should probably look like this:

```text
autoharnessengineering/
  framework/
    config_schema.py
    proposer/
    runner/
    surfaces/
    selection/
    history/
  templates/
    simple_agent/
    langgraph_agent/
    openai_agents_sdk/
  examples/
    pytest_coding_agent/
    harbor_terminal_agent/
  docs/
    research/
    proposal/
```

### Public Templates

At least one starter template should exist for:

- a simple Python agent with `agent.py`, `prompt.md`, `tools.py`

Optional second template:

- a LangGraph/Deep Agents-style harness with middleware/wiring surfaces

## Search Loop Proposal

### Baseline Phase

1. validate config
2. load surfaces
3. run baseline validation
4. run baseline train
5. run baseline holdout
6. optionally run baseline scorecard
7. write baseline to history

### Iteration Phase

For each iteration:

1. build proposer prompt from:
   - experiment config
   - allowed surfaces
   - recent frontier
   - prior failures
   - selected past code / traces
2. run proposer in isolated workspace
3. materialize candidate surfaces
4. run validation
5. if validation fails:
   - record failure
   - mark discard
   - continue
6. run train eval
7. if train does not clear screening threshold:
   - discard
   - continue
8. if holdout is required now:
   - run holdout
9. apply keep/discard policy
10. update frontier and ledger

### Finalization Phase

1. select best promoted candidate
2. run optional scorecard if not yet run
3. produce final report

## Reporting Proposal

The framework should generate:

- append-only `ledger.jsonl`
- `frontier.json`
- a markdown summary for humans

### Final report should include

- baseline metrics
- final metrics
- deltas
- kept and discarded experiments
- top failure strata
- top successful mutation axes
- cost and runtime summary

## Safety And Leakage Controls

### Required In V1

- editable surfaces explicitly declared
- fixed boundary cannot be edited
- holdout cases not shown to proposer as failure artifacts
- evaluator code and benchmark files excluded from edit surface
- train artifacts and traces stored separately from holdout artifacts

### Nice To Have Later

- stronger sandboxing between visible and private data
- audit checks for overfitting patterns
- regex / semantic leakage scans

## Complexity Management

We should resist adding these to v1:

- multi-agent proposer swarms
- distributed scheduling
- embedded governance constitutions
- automatic eval bootstrapping from scratch
- deep UI
- broad non-agent harness support

These are all plausible later, but they dilute the initial framework.

## Suggested V1 Milestones

### Milestone 1: Skeleton

- config loading
- surface abstraction
- candidate workspace materialization
- baseline run support
- history directory layout

### Milestone 2: Pytest Path

- `pytest` runner
- train / holdout splits
- validation hooks
- keep/discard policy
- markdown summary output

### Milestone 3: Proposer Integration

- first proposer backend
- proposer workspace
- proposer logging
- candidate metadata and hypothesis recording

### Milestone 4: Harbor Path

- Harbor runner adapter
- parser for per-task rewards and traces
- concurrency controls

### Milestone 5: Example Repos

- one simple coding agent example
- one more structured agent example with multiple surfaces

## Main Tradeoffs

### Single-file vs multi-surface

Chosen answer:

- framework supports multi-surface
- starter defaults stay close to single-file simplicity

### Holdout every iteration vs periodic holdout

Chosen answer:

- periodic holdout, not every iteration

### Stack-specific vs stack-agnostic

Chosen answer:

- stack-agnostic core with stack-specific templates and adapters

### Research artifact vs reusable OSS framework

Chosen answer:

- reusable OSS framework with research-quality evaluation discipline

## Open Questions

1. Which proposer backend should be first in practice?
2. Should the default config prefer TOML or YAML?
3. How aggressive should the framework be about rerunning noisy candidates?
4. Do we want patch-based candidate capture in addition to full surface snapshots?
5. How much of the proposer reasoning should be stored by default?

## Recommendation

Build v1 as a **new agent-harness evolution framework** with:

- **agent-only scope**
- **declared editable surfaces**
- **simple starter template**
- **`pytest` first, `harbor` second**
- **train every iteration, holdout periodically**
- **filesystem-native experience store**
- **proposer workspace isolation**

This gives us a framework that is:

- simpler than a full general Meta-Harness clone
- more principled than a one-off benchmark script
- more extensible than a one-file-only loop
- well positioned for open source adoption

## Immediate Next Step

If this proposal is accepted, the next document should be a **v1 implementation plan** with:

- concrete module list
- schema definitions
- CLI commands
- MVP milestone breakdown
- first example template choice
