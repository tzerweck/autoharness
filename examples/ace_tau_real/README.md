## ACE TAU Real

This example is the real-ACE integration target for AutoHarness.

It points at the clean ACE `main` snapshot in:

- `../../agentic-context-engine-22-04`

This is intentionally a **big-change lane**. It uses a single editable code
surface rooted at:

- `ace/`

The benchmark wrapper now executes real `tau2` airline tasks through
AutoHarness's script-runner path while keeping AutoHarness as the only outer
loop owner.

Available experiment configs:

- `experiment.toml` for `ace_static`
- `experiment_plain.toml` for the no-ACE control path on the same runner
- `experiment_robust.toml` for `ace_static` with repeated holdout trials
- `experiment_plain_robust.toml` for the no-ACE control with repeated holdout trials
- `experiment_promotion.toml` for the full official airline test holdout with `2` trials per case
- `experiment_plain_promotion.toml` for the plain control on that same promotion-quality holdout

The preferred runtime is a dedicated local venv:

- interpreter: `agentic-context-engine-22-04/.venv/bin/python`
- Python: `3.12`

The validation hook imports the real ACE modules, so the ACE snapshot needs its
own dependencies available inside that venv.

For immediate local progress, the helper wrapper
`examples/ace_tau_real/eval/run_with_ace_python.py` can also fall back to the
already-populated sibling ACE venvs if the local venv exists but is not fully
bootstrapped yet.

Current focus:

- keep evaluation ownership in AutoHarness
- keep task manifests fixed
- let the proposer make large ACE code changes inside an approved surface

Bootstrap helper:

```bash
./examples/ace_tau_real/bootstrap_ace_venv.sh
```

That script creates `agentic-context-engine-22-04/.venv`, installs the core
ACE runtime deps, installs local `tau2` with the `knowledge` extra if
available, and then installs ACE in editable mode without re-resolving `tau2`
from GitHub.

Model defaults in `experiment.toml`:

- `AUTOHARNESS_ACE_AGENT_MODEL = "gpt-4.1-mini-2025-04-14"`
- `AUTOHARNESS_ACE_USER_MODEL = "gpt-4.1-2025-04-14"`
- `AUTOHARNESS_ACE_REFLECTOR_MODEL = "openai:gpt-4.1-mini-2025-04-14"`
- `AUTOHARNESS_ACE_SKILL_MANAGER_MODEL = "openai:gpt-4.1-mini-2025-04-14"`

The `openai:` prefix is deliberate for the ACE reflection roles so PydanticAI
uses the native OpenAI provider rather than its LiteLLM route.

Recent replay finding:

- the 5-task single-trial holdout is materially noisy for this setup
- use the `*_robust.toml` configs before treating holdout deltas as promotion-quality signal
- for the strongest comparison, use the `*_promotion.toml` configs that evaluate the full official airline test set with 2 trials per holdout case
- the first two plain promotion-quality replays both landed at `0.475`, but `8/20` cases still changed score and `6` of those were guardrails
- the guardrail subset itself moved from `0.455` to `0.545`, so policy-sensitive evaluation is noisier than the whole-holdout mean suggests
- the first two ACE promotion-quality replays landed at `0.425` and `0.45`; aggregate rerun noise was smaller there, but ACE still trails the plain average of `0.475`
- so aggregate mean stability is not enough by itself; keep guardrail review enabled
- the promotion configs now wire `eval/policy_guardrail_task_ids.txt` into AutoHarness policy so future search runs can block automatic promotion on new guardrail failures

Replay helpers:

```bash
./.venv/bin/python examples/ace_tau_real/eval/replay_split.py \
  --config examples/ace_tau_real/experiment_promotion.toml \
  --split holdout \
  --output-dir examples/ace_tau_real/replays/promotion_ace_holdout_01/eval/holdout \
  --train-snapshot-skillbook examples/ace_tau_real/runs/ace-tau-real-airline_20260422_134514/candidates/iter_000_baseline/eval/ace_state/train_snapshot_skillbook.json \
  --dotenv ../.env
```

```bash
./.venv/bin/python examples/ace_tau_real/eval/analyze_replays.py \
  <result.json> <result.json> ...
```

```bash
./.venv/bin/python examples/ace_tau_real/eval/analyze_replays.py \
  --focus-manifest examples/ace_tau_real/eval/policy_guardrail_task_ids.txt \
  <result.json> <result.json> ...
```

Per-case ACE artifacts:

- `ace_learning.json` records whether the skillbook changed and how many skills were present
- `ace_context.json` records the retrieval queries and the exact skill IDs injected into the agent context for that case

Current delta rule:

- `promotion_delta = max(0.05, observed_noise_floor)`
- keep policy-sensitive guardrail cases under separate review even when the aggregate mean improves
