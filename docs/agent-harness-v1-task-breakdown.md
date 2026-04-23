# Agent Harness Evolution Framework: MVP Task Breakdown

Status: MVP Implemented  
Date: April 20, 2026

## Locked Decisions

- automated proposer path: `command`
- fallback/testing proposer: `manual`
- first bundled example: lightweight coding/terminal-style agent
- starter template surfaces: `agent.py`, `prompt.md`, `tools.py`
- bundled eval suite: demonstrative, not benchmark-grade

## Implementation Order

### Phase 0: Repo Bring-Up

Goals:

- package skeleton
- CLI entrypoint
- config loader
- normalized experiment model
- example/template directories

Tasks:

- create `pyproject.toml`
- create `autoharness/cli.py`
- create config schema and normalization modules
- create starter example and template
- document the current state in `README.md`

Exit criteria:

- `python -m autoharness.cli validate-config <config>` works

### Phase 1: Store + Baseline Materialization

Goals:

- initialize canonical run directory
- snapshot baseline surfaces
- create ledger and frontier files

Tasks:

- implement run-directory creation helpers
- implement candidate directory creation
- implement baseline surface snapshot writer
- implement JSON / JSONL writing helpers

Exit criteria:

- baseline can be materialized into a run directory without evaluation

### Phase 2: Validation

Goals:

- validate candidate harnesses before running evals

Tasks:

- implement `python_import` validator
- parse `module:symbol` entrypoints
- verify `build_agent()` returns a non-null object
- persist validation outputs to candidate directories

Exit criteria:

- baseline and edited candidates can pass/fail validation deterministically

### Phase 3: Pytest Runner

Goals:

- execute train and holdout cases through `pytest`
- normalize per-case results

Tasks:

- implement pytest command construction
- add bundled pytest plugin for machine-readable reporting
- normalize case and split results
- persist train and holdout summaries

Exit criteria:

- example project can run train and holdout end-to-end

### Phase 4: Selection + Reporting

Goals:

- screen candidates
- promote or discard them
- update the frontier

Tasks:

- implement screening policy
- implement holdout promotion logic
- implement frontier updates
- render markdown summaries

Exit criteria:

- baseline and one candidate can be compared and promoted correctly

### Phase 5: Proposer Backends

Goals:

- allow humans and external agent CLIs to propose edits

Tasks:

- implement `manual` proposer contract
- implement `command` proposer workspace contract
- build filtered proposer context bundle
- capture proposer session metadata

Exit criteria:

- one automated command-based iteration can run end-to-end

### Phase 6: Hardening

Goals:

- improve test coverage
- tighten leakage controls
- support resume/restart

Tasks:

- add integration tests for success and failure paths
- prevent holdout artifacts from leaking into proposer context
- implement resume behavior
- improve error reporting and diagnostics

Exit criteria:

- the MVP can be run repeatedly on the bundled example without manual cleanup

## Implemented Highlights

- Pydantic config models and normalization
- baseline plus iterative orchestration
- `pytest` and `script` runners
- per-case and batch pytest execution paths with a bundled reporting plugin
- `python_import` and `script` validation
- `command` and `manual` proposer backends
- filtered proposer context bundles with ranked frontier history
- candidate diffs and run reports
- run-state persistence and resume support
- frontier state persistence including visible `screened_in` candidates
- integration tests covering baseline, iteration, CLI run, resume, manual proposer, module-attr surfaces, script runner behavior, batch pytest execution, and frontier visibility
- first benchmark-backed tau2 airline integration with external-checkout adapter helpers and runtime custom-agent registration

## Remaining Higher-Value Work

1. Harbor runner integration.
2. Curated real tau2 task manifests plus the first airline baseline run.
3. Multi-candidate search and frontier expansion beyond one proposal per iteration.
4. Stronger structured proposer contracts for agent CLI backends.
5. Performance tuning and artifact strategy for very large eval suites.
