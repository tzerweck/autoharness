# Automated Harness Engineering Research Notes

Status: April 20, 2026

## Goal

Design an open-source system that can automatically create and improve an agent harness for many domains, not just one benchmark. The system should search over harness code around a fixed base model, run evaluations, preserve rich experience from prior runs, and help humans steer the search without hand-editing every candidate harness.

## Important Correction

The paper initially looked like "paper only, no code", but that is no longer true as of April 20, 2026:

- The paper is public: [Meta-Harness: End-to-End Optimization of Model Harnesses](https://arxiv.org/abs/2603.28052)
- The official reference repo is public: [stanford-iris-lab/meta-harness](https://github.com/stanford-iris-lab/meta-harness)
- The Terminal-Bench artifact repo is public: [stanford-iris-lab/meta-harness-tbench2-artifact](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact)

So the question is no longer "can we recreate it from scratch from the paper alone?" The better question is "what parts should we reuse directly, what parts should we generalize, and what repo should we build that is meaningfully broader than the official release?"

## Source Snapshot

- Paper: [arXiv 2603.28052](https://arxiv.org/abs/2603.28052)
- Official Meta-Harness framework: [stanford-iris-lab/meta-harness](https://github.com/stanford-iris-lab/meta-harness)
- Official TB2 evolved harness artifact: [stanford-iris-lab/meta-harness-tbench2-artifact](https://github.com/stanford-iris-lab/meta-harness-tbench2-artifact)
- Minimal autonomous research loop: [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- Minimal autonomous agent-harness loop: [kevinrgu/autoagent](https://github.com/kevinrgu/autoagent)

## What Meta-Harness Actually Contributes

The core contribution is not just "an agent edits code and reruns evals." The paper's real idea is a specific outer-loop design:

1. A coding agent proposes new harness code.
2. A separate evaluator runs the candidate on a search set.
3. The system logs all candidate code, scores, and raw execution traces to disk.
4. Future proposals can selectively inspect the full history through the filesystem.
5. The base model stays frozen; only the harness changes.

The key claim is that harness search needs much richer feedback than normal prompt/text optimization. The paper argues that summary-only or score-only methods throw away the information needed to connect a failure to a concrete harness decision.

### Why This Matters

Meta-Harness is fundamentally about credit assignment across long-horizon agent behavior. It treats code, traces, and scores as first-class optimization signals.

The paper shows three especially important ideas:

- Full-history access beats compressed summaries.
- Raw execution traces matter more than scalar scores.
- Search over executable harness code is a better abstraction than search over prompts alone.

## Paper Details Worth Reusing

### 1. Filesystem As Experience Store

This is the strongest reusable idea. Instead of packing prior runs into one prompt, the proposer gets a queryable directory of:

- candidate source code
- evaluation scores
- execution traces
- summaries/frontier files

This makes the proposer non-Markovian. In the paper's TerminalBench-2 run, the proposer read a median of 82 files per iteration and split attention roughly evenly between prior source code and execution traces.

### 2. Evaluator Outside The Proposer

The proposer should not own benchmark execution. The paper explicitly recommends automating evaluation outside the proposer. This keeps the search loop simple and makes failures cheap to classify.

### 3. Cheap Validation Before Expensive Eval

Before running a real benchmark, candidate harnesses should pass a tiny validation test:

- import works
- required interface exists
- basic execution path works

This is crucial in expensive domains like coding agents.

### 4. Held-Out Test Set Separation

Meta-Harness evolves on a search set and only evaluates final candidates on held-out test data. This is a non-negotiable principle for any serious open-source framework.

### 5. Pareto Selection Instead Of One Scalar

The paper does not force a single objective everywhere. In some settings it reasons over accuracy and context cost jointly, then lets the proposer discover different operating points on the frontier. This is better than pretending every domain reduces to one number.

### 6. Skill-Driven Search

The proposer is guided by a domain-specific skill. The paper's Appendix D is blunt that skill quality is one of the strongest practical levers. The skill should constrain boundaries and outputs, not over-script diagnosis.

### 7. Onboarding For New Domains

The official repo now ships an `ONBOARDING.md` flow. This is important because Meta-Harness is not actually domain-free. It is domain-adaptable. That means a serious framework needs:

- a domain intake process
- an explicit harness boundary
- an explicit evaluation plan
- leakage controls
- budget declarations

## What The Official Meta-Harness Repo Adds

The public `stanford-iris-lab/meta-harness` repo changes the landscape. It confirms several implementation choices that were only implied in the paper:

- the public release is framed as a reusable framework, not just a paper artifact
- it includes onboarding for adapting the method to a new domain
- it includes two reference experiments
- it uses a proposer wrapper (`claude_wrapper.py`) that logs tool calls, file reads/writes, token usage, and artifacts

This means we do not need to rediscover the entire architecture. We can instead decide whether to:

- build on top of the official framework
- fork and generalize it
- or design a new framework that keeps the same core principles but avoids being tightly coupled to Claude Code and their example layout

## What The TB2 Artifact Suggests

The separate Terminal-Bench artifact shows what a discovered harness can look like in practice.

Two especially reusable patterns stand out:

- environment bootstrapping: gather sandbox facts before the task loop starts and inject them into the prompt
- terminal execution efficiency: marker-based polling to stop waiting early when commands finish

This is useful because it shows that harness evolution can discover relatively small systems ideas with large downstream impact. The winning change is not necessarily a giant architecture rewrite.

## What `autoresearch` Contributes

`karpathy/autoresearch` is much simpler than Meta-Harness, but the simplicity is instructive.

### Strong reusable ideas

- one primary editable artifact
- fixed evaluation budget per run
- baseline run first
- keep/discard rule based on measured improvement
- human edits `program.md`, not the evolving artifact directly
- cheap results ledger (`results.tsv`)

### Why it matters

It proves that a small, opinionated loop is often easier for agents to work with than a very flexible framework. It also shows the value of:

- hard constraints
- reviewable diffs
- narrow edit surface
- deterministic run protocol

### Limitation

`autoresearch` is not a general harness-engineering framework. It is closer to autonomous experiment management around one file and one metric.

## What `autoagent` Contributes

`kevinrgu/autoagent` is much closer to the product direction you are describing.

### Strong reusable ideas

- explicit split between human-controlled `program.md` and model-edited `agent.py`
- fixed adapter boundary the meta-agent must not modify
- Harbor task format for evaluations
- score-driven hill climbing over agent harnesses
- clear mutation axes: prompt, tools, agent construction, orchestration
- benchmark tasks as reusable datasets

### Why it matters

This repo is already almost "Meta-Harness light for coding agents." It shows a practical way to define:

- harness under test
- adapter boundary
- task format
- scoring
- run logging

### Limitation

The repo is still benchmark-oriented and relatively narrow:

- single-file harness assumption
- Harbor-specific task setup
- limited history/query tooling compared with Meta-Harness
- no strong domain onboarding layer

## Shared Pattern Across All Three Systems

These projects independently converge on the same core pattern:

1. Keep the base model mostly fixed.
2. Restrict the editable surface.
3. Run the evaluator outside the proposer.
4. Force an initial baseline.
5. Log every run.
6. Keep or discard based on measured outcomes.
7. Let the human steer the meta-loop, not every candidate.

That convergence is a strong signal. Our repo should probably preserve these invariants.

## What A General Open-Source System Needs

If the goal is "whatever domain", then the repo should probably be organized around pluggable abstractions, not one benchmark.

### Recommended core abstractions

- `DomainSpec`
  - task unit
  - fixed components
  - editable harness boundary
  - search budget
  - search-set and held-out-set definitions
  - metrics and secondary metrics
  - leakage risks

- `HarnessAdapter`
  - create baseline candidate
  - validate candidate
  - expose editable files
  - declare interface contract

- `Evaluator`
  - run candidate on search set
  - collect raw traces
  - compute metrics
  - write canonical logs

- `ExperienceStore`
  - canonical directory per candidate
  - source snapshot
  - scores
  - traces
  - metadata
  - summaries/frontier views

- `ProposerAdapter`
  - wrapper for Claude Code, Codex, or other coding agents
  - tool call logging
  - file access logging
  - candidate emission contract

- `SelectionPolicy`
  - scalar best
  - Pareto frontier
  - keep/discard rules
  - noise-aware rerun policy

- `HistoryCLI`
  - list top candidates
  - diff candidate code
  - compare metrics
  - inspect failures
  - query traces

## Design Options For Our Repo

### Option A: Faithful Meta-Harness Clone

Build a near-reproduction of the paper and official repo, but with cleaner docs and maybe broader proposer support.

Pros:

- most faithful to the paper
- lowest conceptual risk
- easiest to explain academically
- easiest to benchmark against official results

Cons:

- may be redundant now that the official repo is public
- can inherit their coupling to specific proposer workflows
- may still feel more like a research release than a general framework

### Option B: `autoagent`-Style General Harness Lab

Build a minimal system focused on agent harness evolution with:

- one editable harness file
- one benchmark/task format
- one meta-agent prompt file
- one results ledger

Pros:

- extremely simple to adopt
- fast to open source
- easy for coding agents to operate

Cons:

- too narrow for "whatever domain"
- weak support for non-agent domains
- not enough structure for cross-domain reproducibility

### Option C: Hybrid Framework

Use Meta-Harness principles as the core architecture, but package them with the ergonomic simplicity of `autoresearch` and `autoagent`.

Concretely:

- Meta-Harness-style experience store and evaluator separation
- `autoresearch`-style keep/discard loop and compact result ledger
- `autoagent`-style fixed harness boundary and benchmark/task format
- official Meta-Harness-style onboarding for new domains

Pros:

- broad enough to matter
- simple enough to adopt
- differentiated from the official repo
- strongest open-source story

Cons:

- requires sharper product decisions up front
- more design work before implementation

## Recommended Direction

Option C looks strongest.

The repo should not try to be "the Meta-Harness paper code again." The official authors now have that lane. The more defensible open-source angle is:

"A general harness-evolution framework that standardizes domain onboarding, evaluation, logging, and proposer integration across many domains."

That gives us a clearer identity:

- not just one paper artifact
- not just one benchmark
- not just one coding-agent loop

## What We Should Reuse Directly

- Meta-Harness idea of full-history filesystem access
- cheap validation gate before full eval
- held-out test discipline
- domain onboarding spec
- proposer wrapper with rich logging
- `autoresearch` baseline-first and keep/discard discipline
- `autoagent` fixed adapter boundary
- benchmark/task dataset abstraction from Harbor-style tasks where relevant

## What We Should Probably Change

- do not hard-couple the framework to Claude Code
- do not hard-couple task definitions to Harbor only
- do not require a single editable file in every domain
- do not make proposer prompts the only control surface; support declarative domain specs
- do not optimize only one scalar if the domain has real tradeoffs

## What A Good First Version Probably Is

The first credible version is not "all domains." It is:

- one core framework
- one domain spec format
- one proposer adapter
- one or two reference domains
- one canonical experience-store schema
- one query CLI

A good launch shape would be:

- reference domain 1: coding/terminal agent
- reference domain 2: retrieval or memory-heavy non-coding task

That would demonstrate that the framework is genuinely cross-domain instead of just a rebranding of `autoagent`.

## Domain Fit Criteria

Not every domain is a good fit. Based on the paper and official onboarding, the system is strongest when:

- tasks are repeated and measurable
- harness choices matter over multiple steps
- the base model is mostly fixed
- there is a real evaluator
- there are recurring failure patterns
- there are traces worth inspecting

It is a weak fit when:

- success is mostly subjective
- there is no stable benchmark
- the main improvement comes from swapping the model rather than changing the harness

## Open Questions For Discussion

1. Do we want to build on top of the official Meta-Harness repo, or create a new repo with our own abstractions?
2. Should our first-class unit be "agent harnesses" specifically, or broader "model harnesses" including retrieval/memory systems?
3. How opinionated should the editable boundary be: single file, fixed directories, or arbitrary declared files?
4. Should we standardize on one task format first, such as Harbor-style tasks, or define our own domain spec and allow adapters?
5. Do we want one proposer backend initially, or an abstraction layer for Claude Code, Codex, and others from day one?
6. Is the first open-source release meant to be a research framework, a benchmark harness lab, or an end-user product for self-improving agents?

## Working Conclusion

Yes, we can recreate the essential Meta-Harness method. More importantly, we no longer need to recreate it blindly because the paper authors have now published a reusable reference implementation. The real opportunity is to build a cleaner cross-domain framework that combines:

- Meta-Harness research rigor
- `autoresearch` simplicity
- `autoagent` benchmark pragmatism

That is the most promising foundation for an open-source repo worth publishing.
