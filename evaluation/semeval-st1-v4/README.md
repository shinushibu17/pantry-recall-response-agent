# ST1 example-count and model comparison

This experiment follows the preserved [title-aware v3](../semeval-st1-v3/README.md).
It tests two changes independently while retaining the v3 title-plus-full-text
input, prompt, taxonomy, category-ID tool schema, temperature 0 and 256-token
output limit. It does not change the deployed pantry agent.

## Completed test regression — September 14, 2026

Nova Pro raised the ST1 score to **0.765878** and correctly classified the product
category on **820/997 reports**. Its requests match v3 exactly except for model ID.

| Metric | Previous v3: Nova Lite | Selected v4: Nova Pro |
| --- | ---: | ---: |
| ST1 composite score (0–1, not accuracy) | 0.735795 | **0.765878** |
| Hazard macro F1 | 0.771158 | 0.777598 |
| Product macro F1 on hazard-correct rows | 0.700432 | 0.754159 |
| Hazard-correct rows | 938 | 947 |
| Hazard accuracy | 94.08% | **94.98%** |
| Product accuracy | 72.92% | **82.25%** |
| Both categories correct | 68.71% | **78.13%** |
| Invalid outputs | 0 | 0 |
| Final error rows | 0 | 0 |
| Request attempts, including retries | 997 | 1,122 |

All metrics use all 997 test rows except the explicitly conditional product F1.
Nova Pro corrected 105 product predictions and regressed on 12, for a net gain
of 93 (9.33 percentage points). It corrected 21 hazard predictions and regressed
on 12. Conditional product F1 uses different hazard-correct cohorts. The remaining
177 wrong product predictions and 50 wrong hazard predictions are preserved.

The test run encountered **125 ThrottlingException attempts**; every affected
row succeeded within the frozen infrastructure retry limit. Zero final error
rows does not mean every API attempt succeeded. The run lasted from 17:51:46
to 17:56:50 UTC, including preparation and retries. Reported successful-response
usage was 5,583,783 input tokens and 25,603 output tokens (5,609,386 total).
These are observed run statistics, not a latency benchmark or billing statement.
The model change also means token totals alone do not establish equal cost.

[Verification](verification.json) reconstructed all **2,127 requests**, re-parsed
saved responses, reproduced all three new scores and verified **55 earlier
artifact hashes** unchanged. All 1,562 Pro validation/test requests were also
checked against v3 and differed only in model ID. This audit was performed by
the builder; it is not independent certification. Selection and regression
limits are described below.

## Evidence

- [Frozen selection decision](decision.json), [selected test protocol](test-protocol.json),
  [metrics and paired changes](comparison.json), [Nova Pro access check](access-check.json).
- Lite validation: [results](validation-lite-eight/results.json),
  [predictions](validation-lite-eight/predictions.csv), [responses](validation-lite-eight/responses.jsonl).
- Pro validation: [results](validation-pro-four/results.json),
  [predictions](validation-pro-four/predictions.csv), [responses](validation-pro-four/responses.jsonl).
- Selected test: [results](test-regression-pro-four/results.json),
  [predictions](test-regression-pro-four/predictions.csv), [responses](test-regression-pro-four/responses.jsonl),
  [run timestamps](test-regression-pro-four/run.json).
- [Publication hashes](publication-manifest.json) bind the package. Each phase
  also contains original per-row hashes in `record-manifest.json`.

## Validation result

| Candidate (565 reports each) | ST1 score | Hazard accuracy | Product accuracy | Request attempts |
| --- | ---: | ---: | ---: | ---: |
| Prior v3: Lite, four examples | 0.723985 | 93.27% | 70.09% | 565 |
| Lite, eight examples | 0.743368 | 93.63% | 69.38% | 565 |
| **Pro, four examples** | **0.785010** | **93.98%** | **78.05%** | 597 |

Nova Pro won the frozen selection rule. All 565 rows in both new candidates
returned valid category IDs, with zero final error rows. Nova Pro encountered
32 throttled attempts that succeeded on bounded infrastructure retries. No
model output was repaired or retried for its content. Eight examples improved
Lite's composite score but slightly reduced its product accuracy; that candidate
was not selected for a test run.

The [combined offline suite](harness-tests.json) passed **137 tests**: 112 pantry
tests and 25 benchmark harness tests, with no failures, errors or skips. All 18
frozen pantry scope cases also passed. These tests use synthetic data and stubbed
model responses; live model results are recorded separately.

## Frozen comparison

| Candidate | Model | Retrieved training examples | Change from v3 |
| --- | --- | ---: | --- |
| `lite-eight` | `amazon.nova-lite-v1:0` | 8 | More examples |
| `pro-four` | `amazon.nova-pro-v1:0` | 4 | Different model |

Both use the same training-only TF-IDF retrieval, weighted 70% title and 30%
body similarity. Target title and full text are not truncated. Each training
example includes its title, excerpt, fine annotations and category labels.
Target annotations are excluded; exact normalized target bodies and duplicate
training bodies are excluded from example selection. Related reports may still
span the organizer's original splits. The model decides both categories;
there are no new label overrides or manual corrections.

The [plan](plan.json) was frozen before validation inference. Both candidates
run once on all 565 validation reports. Highest unrounded official ST1 score
wins, with ties resolved by fewer invalid/error rows, then `lite-eight`.
The winner must strictly exceed v3's **0.7239850784928603** validation score
before one 997-report test regression is permitted. Otherwise v3 is retained
without another test run. No additional candidates are added to this experiment.

Malformed outputs remain invalid without repair or content retries. Infrastructure
errors permit at most three attempts; all attempts are recorded. Invalid/error
rows retain the original sentinel in both fields and remain in the denominator.
The ST1 metric is the mean of hazard macro F1 and product macro F1 on the
hazard-correct subset; it is not an accuracy percentage. Conditional subsets
can differ between systems.

All three previous test results have been seen. This pass inspected validation
errors to motivate the comparison. Repeated validation selection and exposed-test
regression do not establish fresh held-out generalization, model contamination
status, leaderboard rank or pantry workflow accuracy. ST2 is not evaluated.

## Reproduce

Acquire the pinned CSVs as described in the [initial benchmark guide](../semeval-st1/README.md).
Earlier frozen code, predictions and manifests remain unchanged. Nova Pro access
was checked with a tiny non-dataset request before freezing this comparison.
The [AWS model documentation](https://docs.aws.amazon.com/nova/latest/userguide/what-is-nova.html)
lists the Nova Lite and Nova Pro identifiers.

```powershell
uv sync --frozen --group evaluation
uv run --frozen --group evaluation python -m tools.semeval_capacity run --protocol evaluation/semeval-st1-v4/validation-lite-eight-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_capacity run --protocol evaluation/semeval-st1-v4/validation-pro-four-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_capacity select
```

`prepare` refuses to overwrite the frozen plan. `select` records the decision
and freezes a test protocol only if the winner exceeds the incumbent. A selected
test protocol can be run and scored with:

```powershell
uv run --frozen --group evaluation python -m tools.semeval_capacity run --protocol evaluation/semeval-st1-v4/test-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_capacity score --protocol evaluation/semeval-st1-v4/test-protocol.json
```

Run records are stored under ignored `outputs/semeval-st1-v4/`. Cached responses
are reused, not replaced. Protocol hashes bind code, data, tests and dependency
lock; request hashes bind the full title/text and training-example payload.

Dataset and scoring attribution: [SemEval 2025 Task 9 organizers](https://food-hazard-detection-semeval-2025.github.io/).
The [CC BY-NC-SA 4.0 data terms](../semeval-st1/DATA-LICENSE.md) remain separate
from the code license. This is an adapted title-plus-text classification experiment.
