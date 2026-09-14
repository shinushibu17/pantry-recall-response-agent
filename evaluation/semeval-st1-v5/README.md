# Complete training taxonomy: target ST1 0.90

The requested target is **an ST1 composite score of 0.90**, not 90% product or
hazard accuracy. This experiment follows [v4](../semeval-st1-v4/README.md), whose
test score was 0.765878. The target is an aspiration; only completed evaluations
can establish whether it is reached. The deployed pantry application is unchanged.

## Completed test result — September 14, 2026

**ST1 improved to 0.789229; the requested 0.90 target was not reached.** The
remaining gap is 0.110771. The selected Nova Pro run scored all 997 test reports
with unchanged labels and no invalid outputs or final error rows.

| Metric | v4 Nova Pro | v5 full-taxonomy Nova Pro |
| --- | ---: | ---: |
| ST1 composite (0–1, not accuracy) | 0.765878 | **0.789229** |
| Hazard macro F1 | 0.777598 | 0.781372 |
| Product macro F1 on hazard-correct rows | 0.754159 | 0.797086 |
| Hazard-correct rows | 947 | 953 |
| Hazard accuracy | 94.98% | **95.59%** |
| Product accuracy | **82.25%** | 82.05% |
| Both categories correct | 78.13% | 78.54% |
| Invalid outputs / final error rows | 0 / 0 | 0 / 0 |
| Request attempts, including retries | 1,122 | 1,142 |

The composite gain does not mean every metric improved. Product predictions
corrected 23 earlier errors but introduced 25, a net loss of two correct product
categories. Hazard predictions corrected nine and regressed on three, a net
gain of six. Conditional product F1 uses different hazard-correct cohorts.
The 179 wrong product predictions and 44 wrong hazard predictions are preserved.

The run retried 145 throttled attempts within the existing infrastructure limit.
It reported 10,679,815 input tokens and 25,608 output tokens (10,705,423 total),
versus 5,583,783 input tokens for v4. It ran from 18:50:54 to 19:01:51 UTC,
including preparation and retries. These are service-reported observations,
not a billing statement or controlled latency benchmark. The larger prompt
costs substantially more input tokens for a modest score gain.

[Verification](verification.json) reconstructs all 2,127 validation/test requests
from training data and target title/text, rebuilds the full taxonomy from training,
re-parses responses and reproduces all three scores. It also checks 80 earlier
manifested artifacts unchanged. This is builder verification, not an independent
audit or fresh held-out evaluation. No further candidates were added to this
frozen experiment after seeing its test result.

## Evidence

- [Selection decision](decision.json), [test protocol](test-protocol.json),
  [comparison, target status and paired errors](comparison.json), [model access checks](access-checks.json).
- Pro validation: [results](validation-pro-taxonomy/results.json),
  [predictions](validation-pro-taxonomy/predictions.csv), [responses](validation-pro-taxonomy/responses.jsonl).
- Nova 2 validation: [results](validation-nova2-taxonomy/results.json),
  [predictions](validation-nova2-taxonomy/predictions.csv), [responses](validation-nova2-taxonomy/responses.jsonl).
- Selected test: [results](test-regression-pro-taxonomy/results.json),
  [predictions](test-regression-pro-taxonomy/predictions.csv), [responses](test-regression-pro-taxonomy/responses.jsonl),
  [timestamps](test-regression-pro-taxonomy/run.json).
- [Publication hashes](publication-manifest.json) bind the package; each phase
  also includes the original per-row hashes in `record-manifest.json`.

## Completed validation

| Configuration (565 reports each) | ST1 score | Hazard accuracy | Product accuracy |
| --- | ---: | ---: | ---: |
| Prior v4 Nova Pro | 0.785010 | 93.98% | 78.05% |
| **Full-taxonomy Nova Pro** | **0.796612** | **94.69%** | **78.05%** |
| Full-taxonomy Nova 2 Lite | 0.767982 | 94.51% | 77.52% |

Nova Pro won; Nova 2 Lite did not improve on the incumbent. Both runs returned
565 valid outputs with no final error rows. There were 614 total attempts for
Pro and 567 for Nova 2 Lite, including infrastructure retries. Pro's validation
hazard macro F1 was 0.836502 and conditional product macro F1 was 0.756721.
The improvement was modest and **did not reach the 0.90 ST1 target**.

## Frozen method

Two candidates share the same new prompt and differ in model:

- `pro-taxonomy`: `amazon.nova-pro-v1:0`.
- `nova2-taxonomy`: `us.amazon.nova-2-lite-v1:0`.

Both include all **1,022 distinct product terms and 128 hazard terms** found in
the training annotations, grouped under their observed category IDs. Unlike
the previous eight-fine-label-per-category summary, rare training mappings are
retained. Terms observed under multiple categories stay in each category; the
code does not silently choose one mapping. No validation or test annotation
enters the taxonomy or model request.

The prompt also handles title/body disagreement. An explicit recall description
in the body takes priority when it identifies a different product from the
title; titles still supply names omitted by the body. Training conventions guide
category selection, while ingredients, packaging and unrelated page text are
distinguished from the affected product.

Four training examples remain selected by the v3/v4 TF-IDF index, with 70% title
and 30% body similarity. Training-only fitting, exact normalized target-body
exclusion, duplicate training-body exclusion, full target title/text, temperature
0, 256 output tokens, category-ID tool schema and strict parsing are unchanged.
Two workers replace four to reduce simultaneous request load. This is a prompt
and model experiment, not fine-tuning or an evaluation of the Strands workflow.

The [plan](plan.json) freezes both candidates on all 565 validation reports.
Selection uses highest unrounded ST1 score; ties use fewer invalid/error rows,
then `pro-taxonomy`. The winner must strictly beat v4's **0.7850097662137301**
validation score before one 997-report test regression is run. Product/hazard
accuracy tradeoffs are reported separately. The user's metric clarification
was incorporated before the plan was frozen and before any dataset inference.

Invalid or failed rows retain the original sentinel in both categories and
remain in the full denominator. No content repair or content retries are allowed.
Up to three attempts are allowed for infrastructure failures, and all attempts
are preserved. Numeric usage fields are aggregated; complete service usage
objects remain in individual response records.

## Data quality and interpretation

Validation inspection found a real title/body disagreement: validation row 3 has
a sunflower-seed title and an ice-cream recall body; its frozen label follows
the body. Validation row 78 describes cilantro but is labelled as sauces/spreads,
which is flagged as a possible annotation or alignment issue. These observations
motivate general evidence handling; there are no row-ID rules or label changes.
They do not prove a numerical ceiling on achievable performance.

All four prior test results have been seen. Repeated validation optimization
and another test regression are **not fresh held-out evidence**. ST1 averages
hazard macro F1 with product macro F1 on hazard-correct rows; it is not accuracy.
Rare categories matter strongly, and conditional product cohorts may differ
between models. No leaderboard rank, contamination-free data, autonomous handling
ability or measured pantry outcome is claimed. ST2 is not evaluated.

For scale, the [organizers' report, Table 2](https://aclanthology.org/2025.semeval-1.325.pdf)
lists a highest ST1 score of 0.8223 among the 27 systems with submitted system
description papers. That is historical context, not a ceiling or a directly
comparable rank for this exposed-test experiment. A 0.90 target exceeds that
published result; it cannot be promised from prompt or model substitutions.

## Reproduce

Acquire the pinned CSVs using the [original benchmark guide](../semeval-st1/README.md).
Earlier code and manifests stay frozen. Nova Premier could not be invoked using
the checked identifiers. A Sonnet tool request required account use-case details,
so Sonnet was not evaluated on dataset rows. Nova 2 Lite passed a synthetic
classification-tool check before this plan was frozen.

```powershell
uv sync --frozen --group evaluation
uv run --frozen --group evaluation python -m tools.semeval_taxonomy run --protocol evaluation/semeval-st1-v5/validation-pro-taxonomy-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_taxonomy run --protocol evaluation/semeval-st1-v5/validation-nova2-taxonomy-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_taxonomy select
```

`prepare` refuses to overwrite a frozen plan. `select` records the decision;
only an improvement produces a test protocol. For that protocol:

```powershell
uv run --frozen --group evaluation python -m tools.semeval_taxonomy run --protocol evaluation/semeval-st1-v5/test-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_taxonomy score --protocol evaluation/semeval-st1-v5/test-protocol.json
```

Raw records live under ignored `outputs/semeval-st1-v5/`; cached responses are
reused rather than replaced. Protocol hashes bind code, data, tests and `uv.lock`;
request hashes bind complete inputs and training examples.

The [offline suite](harness-tests.json) passed **145 tests** and all 18 frozen
pantry scope cases. These are synthetic/stubbed checks, separate from live scores.

Dataset/scorer: [SemEval 2025 Task 9 organizers](https://food-hazard-detection-semeval-2025.github.io/).
The [CC BY-NC-SA 4.0 data terms](../semeval-st1/DATA-LICENSE.md) apply separately
from the code license. Model integration follows the
[AWS Nova 2 inference documentation](https://docs.aws.amazon.com/nova/latest/nova2-userguide/core-inference.html).
