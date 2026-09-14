# ST1 v8: time-bounded DeepSeek / Qwen category combinations

Both validation runs completed. The best prelisted combination was **h-v5-p-deepseek** at **0.807327 ST1**. The required validation gain was met. The decision occurred after the frozen 20:40 UTC test-launch cutoff, so **no test run was launched**.

The best completed observed 997-report test regression remains
[v5: **0.789229**](../semeval-st1-v5/README.md).
The requested **0.90 ST1 target was not reached**. The scores below are validation
scores; they cannot replace a test result.

| Phase | Observed / planned reports | Official validation ST1 | Invalid / error rows |
| --- | ---: | ---: | ---: |
| validation-deepseek | 565 / 565 | 0.796325 | 0 / 0 |
| validation-h-deepseek-p-deepseek | 565 / 565 | 0.796325 | 0 / 0 |
| validation-h-deepseek-p-qwen | 565 / 565 | 0.735899 | 1 / 0 |
| validation-h-deepseek-p-v5 | 565 / 565 | 0.786419 | 0 / 0 |
| validation-h-qwen-p-deepseek | 565 / 565 | 0.753369 | 1 / 0 |
| validation-h-qwen-p-qwen | 565 / 565 | 0.733694 | 1 / 0 |
| validation-h-qwen-p-v5 | 565 / 565 | 0.742888 | 1 / 0 |
| validation-h-v5-p-deepseek | 565 / 565 | 0.807327 | 0 / 0 |
| validation-h-v5-p-qwen | 565 / 565 | 0.745780 | 1 / 0 |
| validation-qwen | 565 / 565 | 0.733694 | 1 / 0 |

## Frozen comparison

The [plan](plan.json) froze two model runs and eight fixed hazard/product
combinations from v5 Nova Pro, DeepSeek V3.2 and Qwen3 Next 80B A3B. Models used
the same v5 prompt, full training-derived taxonomy, complete target title/text,
and four unchanged training-only retrieval examples. No target annotations were
included in requests. Exact normalized target bodies and duplicate example
bodies were excluded from retrieval per query.

Both new models used temperature 0, maximum 2,048 output tokens, six workers,
and automatic tool choice. The strict parser still required exactly one
`classify_incident` call with two valid category IDs. Qwen's duplicate tool-call
response remains invalid in both fields. No content retries or label repairs
were allowed; infrastructure failures had at most three attempts.

Selection required both complete 565-report model runs, the highest unrounded
ST1 among the eight fixed combinations, a gain of at least 0.005 over v5
validation (0.7966116136945308), and test launch before 20:40 UTC. New calls and
retries stop at 21:00 UTC, the user's 5 p.m. Eastern experiment cutoff. The
[decision](decision.json) preserves the actual outcome. No rule was relaxed
after observing the results.

Combination records bind each category to its parent record hash. If either
selected parent output is invalid, both combined fields remain invalid. These
combinations make no new model calls: their zero attempt counts are not a claim
that the underlying predictions cost nothing. Usage and attempts belong to the
unique direct model runs.

## Evidence and limits

Each completed phase directory contains results, predictions, raw response
records, per-row hashes and execution metadata. Incomplete phases have observed
records and metadata but no full-split score. Protocol files sit beside this
README. [Verification](verification.json) reconstructs recorded requests,
re-parses raw responses, checks parent bindings and complete-split metrics, and
verifies 192 earlier manifested artifacts are unchanged.
The [publication manifest](publication-manifest.json) binds this package.
[159 local tests passed](harness-tests.json).

The plan's exposure note mentions v7 as concurrent; by v8 inference both v7
validation results were complete. V7 had no test run. All six prior test
regressions had already been observed. This remains repeated-validation
development and exposed-test selection, not untouched evaluation or an official
leaderboard result. Seven validation and seven test reports match training
bodies; query-level retrieval exclusions do not establish a globally clean
dataset or rule out foundation-model contamination. ST2 was not evaluated.

OpenAI Terra appeared in the Bedrock catalog but account access was denied.
Only synthetic readiness requests were attempted; no dataset rows were sent to
that model and no access policies were changed. DeepSeek and Qwen passed their
synthetic tool checks before the protocols were frozen.

Data attribution and separate CC BY-NC-SA 4.0 terms are in
[DATA-LICENSE.md](../semeval-st1/DATA-LICENSE.md). The PantryRecall application
continues to use Nova Lite; benchmark results do not change its scope matching
or confirmation workflow.
