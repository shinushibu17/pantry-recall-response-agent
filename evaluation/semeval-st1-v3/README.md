# Title-aware ST1 product classification

This experiment follows the preserved [initial baseline](../semeval-st1/README.md)
and [first validation-selected improvement](../semeval-st1-v2/README.md).
It uses the same Nova Lite model and official scoring function. It changes the
input to **target title plus full report text**, so improvements are not attributable
to model reasoning alone or strictly comparable to a text-only setup. This is
a supplementary classification experiment; the deployed pantry application is
unchanged, and ST2 is not evaluated.

## Completed results — September 14, 2026

The title-weighted candidate won validation and improved the test regression
score to **0.735795**, with **727/997 correct product categories**. No malformed
outputs or API-error rows occurred in either validation run or the test run.

| Validation candidate (565 reports each) | ST1 score | Decision |
| --- | ---: | --- |
| Prior v2 incumbent | 0.665723 | Fixed threshold |
| Title with body-ranked examples | 0.653008 | Below incumbent |
| Title with title-weighted examples | **0.723985** | Selected before test inference |

| Metric on all 997 test reports unless stated | Initial v1 | Retrieval v2 | Title-weighted v3 |
| --- | ---: | ---: | ---: |
| ST1 composite score (0–1, not accuracy) | 0.566941 | 0.679364 | **0.735795** |
| Hazard macro F1 | 0.463246 | 0.736443 | 0.771158 |
| Product macro F1 on hazard-correct rows | 0.670635 | 0.622286 | 0.700432 |
| Hazard-correct rows | 843 | 938 | 938 |
| Hazard accuracy | 84.55% | 94.08% | 94.08% |
| Product accuracy | 66.30% | 65.40% | **72.92%** |
| Both categories correct | 57.87% | 61.48% | 68.71% |
| Invalid outputs | 41 | 0 | 0 |
| API-error rows | 0 | 0 | 0 |

Relative to v2, v3 corrected 125 product predictions and regressed on 50,
a net gain of 75 (7.52 percentage points). Hazard predictions corrected 18 and
regressed on 18. Consequently the two hazard-correct cohorts both contain 938
reports but differ in membership; conditional product F1 compares different
subsets. Rare categories remain difficult: migration hazard has F1 0 on its
single test example. This is improvement, not reliable classification of every
category. No further candidates or test runs were added in this experiment.

The selected test run made 997 model calls without retries, reporting 5,583,783
input tokens and 25,692 output tokens (5,609,475 total). It ran from 17:27:58 to
17:30:59 UTC. This uses more input tokens than v2's 5,171,367; token counts are
service-reported usage, not a billing statement or measured latency benchmark.

The [combined offline suite](harness-tests.json) passed **131 tests** and all
18 pantry scope scenarios. [Artifact verification](verification.json) rebuilt
all 2,127 requests using only training data and target title/text, re-parsed
saved model responses, reproduced all three scores and checked 31 prior artifact
hashes. This was performed by the builder, not an independent evaluator.

## Evidence

- [Validation selection](decision.json), [test protocol](test-protocol.json),
  [machine-readable comparison and paired changes](comparison.json).
- Title candidate: [results](validation-title/results.json),
  [predictions](validation-title/predictions.csv), [responses](validation-title/responses.jsonl).
- Title-weighted candidate: [results](validation-title-weighted/results.json),
  [predictions](validation-title-weighted/predictions.csv), [responses](validation-title-weighted/responses.jsonl).
- Selected test: [results](test-regression-title-weighted/results.json),
  [predictions](test-regression-title-weighted/predictions.csv),
  [responses](test-regression-title-weighted/responses.jsonl),
  [run timestamps](test-regression-title-weighted/run.json).
- [Publication hashes](publication-manifest.json) bind the packaged files.
  Each phase also contains original per-row hashes in `record-manifest.json`.

## Frozen development plan

Inspection of product errors used the validation split. Some source bodies omit
the product named in the title; earlier experiments sent the body alone.
The [development plan](plan.json) fixes two candidates before validation inference:

1. **Title:** include the target title and full text. Keep the previous body-text
   TF-IDF ranking, while adding training titles and fine product/hazard annotations
   to the four retrieved training examples.
2. **Title-weighted:** the same input and examples, ranked by 70% title cosine
   similarity and 30% body-text cosine similarity.

Both retain category-ID tool output and training-derived taxonomy guidance.
They use all 565 validation reports, four examples per report, temperature 0,
256 output tokens and four concurrent requests. Training examples may be
excerpted; target titles and full text are not truncated. The added instruction
uses the title to establish product focus and prefers a specific category when
one covers the product.

Both retrieval indices fit **training data only**. Query labels, fine product/
hazard answers, country and other target metadata are excluded. Exact normalized
target body text and duplicate normalized training examples are excluded per
query. Related notices can still span the organizer's original splits.

Selection uses the highest unrounded official validation score, then fewer
invalid/error rows, then the simpler title candidate. The winner must strictly
beat the fixed prior validation score, 0.6657233276685435, before another test
run is permitted by this plan. Otherwise the incumbent is retained. Both earlier
test results have been seen; any new test result is a **further regression
comparison after test exposure**, not fresh held-out evidence. Repeated use of
validation also limits its independence.

Malformed outputs are not repaired or retried. Infrastructure retries, if any,
are retained. Invalid/error rows remain in the denominator using the original
sentinel policy. No test-score threshold is chosen after seeing new test answers.

## Reproduce

Use the pinned CSV files and existing dependency lock described in the
[original benchmark guide](../semeval-st1/README.md). The evaluation code is
versioned separately so neither earlier frozen implementation is changed.

```powershell
uv sync --frozen --group evaluation
uv run --frozen --group evaluation python -m tools.semeval_product run --protocol evaluation/semeval-st1-v3/validation-title-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_product run --protocol evaluation/semeval-st1-v3/validation-title-weighted-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_product select
```

`prepare` refuses to overwrite the frozen plan. `select` records the validation
decision and, only if it beats the incumbent, freezes a test protocol. For that
selected protocol:

```powershell
uv run --frozen --group evaluation python -m tools.semeval_product run --protocol evaluation/semeval-st1-v3/test-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_product score --protocol evaluation/semeval-st1-v3/test-protocol.json
```

Run and score records are written under ignored `outputs/semeval-st1-v3/`.
Saved predictions are reused, not replaced. Target hashes now bind **both title
and text**; request hashes bind the entire prompt and training-example payload.

## Attribution and limits

Dataset and scorer: [SemEval 2025 Task 9 organizers](https://food-hazard-detection-semeval-2025.github.io/).
Data and derived label vocabulary retain the
[CC BY-NC-SA 4.0 attribution and terms](../semeval-st1/DATA-LICENSE.md), separate
from the code license. Adding title input and labelled training excerpts is an
explicit evaluation adaptation. No organizer endorsement, leaderboard rank,
unseen-model-data claim, pantry field accuracy or autonomous handling capability
is implied.
