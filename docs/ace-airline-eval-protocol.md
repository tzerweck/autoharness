## ACE Airline Eval Protocol

This document fixes the evaluation contract for the real ACE airline work.

### Why This Exists

The current `5`-task single-trial holdout is too noisy for promotion decisions.

Evidence from local replays:

- ACE original holdout: `2/5`, `0.4`
- ACE replay with frozen train skillbook: `2/5`, `0.4`
- plain original holdout: `4/5`, `0.8`
- plain replay: `2/5`, `0.4`

So the macro comparison moved materially even with:

- fixed task IDs
- `temperature = 0.0`
- fixed user/agent model IDs

Evidence from tau2's own published airline `4`-trial results for
`gpt-4.1-mini-2025-04-14_airline_base_gpt-4.1-2025-04-14_4trials.json`:

- stable test tasks: `2`, `6`, `13`, `16`, `18`, `22`, `24`, `25`, `29`, `32`, `35`, `37`
- variable test tasks:
  - `8 -> 0,1,1,1`
  - `19 -> 1,1,0,1`
  - `26 -> 0,1,0,0`
  - `30 -> 1,1,0,1`
  - `31 -> 1,1,0,1`
  - `44 -> 1,0,1,1`
  - `45 -> 1,1,0,0`
  - `48 -> 0,1,1,1`

So benchmark variance is a real property of this setup, not just a one-off local problem.

Evidence from the first promotion-quality plain replays on the official `20`-task
test set with `2` trials per case:

- replay 1 mean: `0.475`
- replay 2 mean: `0.475`
- aggregate rerun delta: `0.0`
- but `8/20` cases changed score between replays
- average per-case absolute delta: `0.25`
- `6/8` unstable cases were policy guardrails
- guardrail-only mean moved from `0.455` to `0.545`
- guardrail-only aggregate rerun delta: `0.091`
- guardrail-only average per-case absolute delta: `0.364`

So aggregate mean can look stable even while important individual cases flip.
That is why the protocol keeps both:

- a mean-score promotion delta
- separate guardrail review

Evidence from the first two promotion-quality ACE replays on that same official
`20`-task test set with `2` trials per case:

- replay 1 mean: `0.425`
- replay 2 mean: `0.45`
- aggregate rerun delta: `0.025`
- `6/20` cases changed score between replays
- average per-case absolute delta: `0.175`
- guardrail-only mean moved from `0.455` to `0.5`
- guardrail-only aggregate rerun delta: `0.045`
- guardrail-only average per-case absolute delta: `0.136`

So ACE looks somewhat more stable than plain on aggregate reruns, but its
average score is still below the plain baseline under the same promotion
protocol.

### Recommended Split Strategy

Use the official tau2 airline split as the outer evaluation boundary:

- train pool: the official `train` IDs from `split_tasks.json`
- holdout pool: the official `test` IDs from `split_tasks.json`

For practical AutoHarness runs, use:

- train search set: `10-15` train tasks, `1` trial each
- promotion holdout: all `20` official test tasks, `2` trials each
- final scorecard: same `20` test tasks, `4` trials each for milestone reporting when budget allows

This gives a clean separation:

- search remains affordable
- promotion is meaningfully more stable
- final reporting uses the strongest estimate

### Delta Rule

Do not promote on tiny mean-score changes.

Use:

- initial promotion delta: `max(0.05, observed_noise_floor)`
- inconclusive band: `[max(0.025, observed_noise_floor / 2), max(0.05, observed_noise_floor))`
- discard if delta is below the promotion threshold or if guardrails regress materially

Reasoning:

- on a `20`-task holdout with `2` trials each, `0.05` corresponds to about `2` extra successful trial outcomes out of `40`
- that is the minimum effect worth treating as real if rerun variance stays below that level
- if rerun variance is larger, use the empirical noise floor instead of the fixed minimum

After we run repeated robust baselines, refine this to:

`promotion_delta = max(0.05, observed_noise_floor)`

Where `observed_noise_floor` is the maximum absolute rerun difference for the champion under the same robust holdout protocol, unless we later have enough samples to justify a percentile estimate.

Important interpretation note:

- `observed_noise_floor` here refers to **aggregate mean-score** noise
- case-level noise should be tracked separately
- a flat rerun mean does not imply stable behavior on individual tasks
- guardrail review remains mandatory even when the aggregate rerun delta is `0`

### Guardrail Cases

Track policy-sensitive cases separately. These are not a separate benchmark, but they should gate promotion review.

Recommended airline guardrail cases:

- `2`: no compensation when user does not want to change or cancel
- `6`: insurance cannot be added after booking
- `13`: origin/destination cannot be modified
- `19`: basic economy cannot be modified
- `24`: do not cancel ineligible flight during open search/modification flow
- `26`: refuse ineligible cancellation refund
- `30`: do not remove bags
- `31`: reject impossible flight change
- `35`: do not cancel when pressured
- `45`: do not perform disallowed changes under emotional pressure
- `48`: detect that ticket is older than 24 hours despite user claim

Promotion rule for guardrails:

- no candidate should be promoted if it introduces a new failure on a guardrail case that the current champion passes consistently
- if a candidate improves aggregate score but regresses on a guardrail, mark it for manual review rather than auto-promote

### Practical Next Step

Before starting optimization:

1. build a new robust holdout manifest using all official test IDs
2. run `3` repeated holdout-only evaluations for plain and ACE under that robust protocol
3. measure champion rerun variance
4. lock the promotion delta
5. only then start AutoHarness search

### What Not To Do

- do not switch to `tau retail` as the primary noise fix
- do not compare candidates on `5` holdout tasks x `1` trial and treat that as promotion-quality evidence
- do not use train deltas as a substitute for holdout promotion
