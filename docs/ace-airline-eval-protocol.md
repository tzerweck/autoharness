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

Evidence from the first two promotion-quality plain replays on the intended
Bedrock/Anthropic stack with `2` trials per case:

- replay 1 mean: `0.575`
- replay 2 mean: `0.5`
- replay 3 mean: `0.45`
- aggregate rerun deltas: `0.075`, `0.125`, `0.05`
- observed aggregate noise floor: `0.125`
- `12/20` cases changed score across the three replays
- observed case-level noise floor: `0.275`
- guardrail-only means: `0.727`, `0.591`, `0.591`
- guardrail-only aggregate noise floor: `0.136`

Evidence from the first two promotion-quality ACE replays on that same
Bedrock/Anthropic stack:

- replay 1 mean: `0.55`
- replay 2 mean: `0.55`
- aggregate rerun delta: `0.0`
- `9/20` cases changed score between replays
- average per-case absolute delta: `0.3`
- guardrail-only mean moved from `0.727` to `0.682`
- guardrail-only aggregate rerun delta: `0.045`

Additional evidence from a second independent ACE Bedrock train snapshot:

- train snapshot 2 produced holdout replay means of `0.625` and `0.625`
- conditional holdout rerun noise for that fixed snapshot was `0.0`
- guardrail-only mean for both snapshot-2 replays was `0.636`

So on the intended Bedrock stack:

- plain replay noise is large: observed aggregate floor `0.125`
- simple ACE holdout rerun noise is low once the train snapshot is fixed: `0.0` on snapshot 1 and `0.0` on snapshot 2
- simple ACE does have train-snapshot variance: snapshot 1 averaged `0.55`, snapshot 2 averaged `0.625`
- the observed ACE train-snapshot shift is `0.075`
- compared with the three plain replays, the stronger ACE snapshot is consistently above the plain mean and above two of the three plain reruns
- guardrail behavior is still noisy, so guardrail review remains mandatory

Evidence from the first RR Bedrock lane:

- RR train replay mean: `0.7` on the `10`-task train subset
- RR holdout replay mean: `0.5`
- RR holdout guardrail-only mean: `0.727`
- RR training was materially slower than the simple reflector path

Additional evidence from a second independent RR Bedrock train snapshot:

- RR train snapshot 2 produced holdout replay means of `0.325` and `0.375`
- RR snapshot-2 guardrail-only means were `0.409` and `0.455`
- observed RR aggregate noise floor across the three holdouts is `0.175`
- observed RR guardrail-only noise floor is `0.318`

So RR does not justify being the baseline or the optimization lane. It is both
weaker and noisier than simple ACE, and it costs materially more to train.

Evidence from the first-pass simplified full official `train -> test` lane:

- fresh plain official-test replay mean: `0.475`
- fresh plain official-test guardrail-only mean: `0.636`
- simple ACE train snapshot 1 mean on the full official `30`-task train split: `0.533`
- simple ACE train snapshot 1 frozen skillbook size: `67`
- simple ACE official-test replay mean on that snapshot: `0.45`
- simple ACE official-test guardrail-only mean on that snapshot: `0.545`
- RR train snapshot 1 mean on the full official `30`-task train split: `0.6`
- RR train snapshot 1 frozen skillbook size: `59`
- RR official-test replay mean on that snapshot: `0.65`
- RR official-test guardrail-only mean on that snapshot: `0.727`

So the simplified full official `train -> test` lane changes the first-pass
ranking materially:

- plain beats the first simple ACE snapshot by `0.025`
- RR beats plain by `0.175`
- RR beats the first simple ACE snapshot by `0.2`

But that simplified lane currently has only one learned train snapshot for
simple ACE and one for RR, so it does not yet have a train-snapshot noise
estimate comparable to the earlier promotion-quality Bedrock lane. That means
the simplified-lane baseline question is sharper than before, but not fully
settled yet.

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

For the Bedrock/Anthropic target stack, the baseline question now depends on
which protocol you mean:

1. on the earlier promotion-quality lane with the smaller train subset, simple ACE looked stronger than RR
2. on the simplified full official `train -> test` lane, RR currently leads on the first pass
3. plain remains the external no-learning control on both lanes
4. the promotion-quality lane still has the better aggregate noise decomposition:
5. plain replay floor: `0.125`
6. simple ACE fixed-snapshot replay floor: `0.0`
7. simple ACE observed train-snapshot shift: `0.075`
8. keep guardrail review mandatory on every lane

Practical implication:

- do not mix the earlier promotion-lane ranking with the simplified-lane ranking
- if the simplified full official `train -> test` protocol is the new benchmark of record, rerun at least one more independent simple ACE train snapshot and one more independent RR train snapshot before declaring the baseline settled
- treat the current simplified-lane RR result (`0.65`) as promising but provisional
- keep Bedrock plain as the external control when judging any future improvement claim

### What Not To Do

- do not switch to `tau retail` as the primary noise fix
- do not compare candidates on `5` holdout tasks x `1` trial and treat that as promotion-quality evidence
- do not use train deltas as a substitute for holdout promotion
