# SemEval ST1: validation-selected improvement

This is a separate Nova Lite classification experiment. The original
[997-row baseline](../semeval-st1/README.md), its 0.566941 score, invalid responses,
frozen prompt and scorer remain intact. The deployed pantry application has not
been changed by this experiment.

## Completed comparison — September 14, 2026

The retrieval variant won the predeclared validation comparison, **0.665723 vs
0.585262**, with zero invalid outputs or API errors in either 565-report run.
Its configuration was frozen before the single 997-report test regression run.

| Test measure | Original baseline | Validation-selected retrieval |
| --- | --- | --- |
| Published ST1 composite score | 0.566941 | **0.679364** |
| Hazard macro-F1 | 0.463246 | 0.736443 |
| Product macro-F1 on hazard-correct rows | 0.670635 | 0.622286 |
| Hazard-correct rows used for conditional product F1 | 843 | 938 |
| Hazard accuracy | 84.55% | 94.08% |
| Product accuracy across all rows | 66.30% | 65.40% |
| Both categories correct | 57.87% | 61.48% |
| Invalid responses | 41 | **0** |
| API error rows / model attempts | 0 / 997 | 0 / 997 |
| Response-reported input tokens | 899,281 | 5,171,367 |
| Response-reported output tokens | 29,112 | 25,712 |

The composite gain is **0.112424 on the 0–1 scale**, driven by better hazard
classification. This is not an accuracy percentage. Product accuracy declined
by nine cases, from 661 to 652 correct. The conditional product F1 columns use
different hazard-correct cohorts, so they do not compare the same subset of rows.
Longer taxonomy guidance and examples also increased input-token use substantially.
No billing-cost or statistical-significance claim is made.

For example, hazard F1 for fraud rose from 0.2727 to 0.8085 on 75 reports; other
hazard rose from 0 to 0.5217 on 26. Migration remained at 0 on its single report.
These are descriptive results from an exposed test set, not proof of general
recall understanding. We stopped after the two planned validation candidates
and the selected test run; no further test-driven tuning is included.

Evidence: [machine-readable comparison](comparison.json),
[schema validation results](validation-schema/results.json),
[retrieval validation results](validation-retrieval/results.json),
[test results and category breakdown](test-regression-retrieval/results.json),
[test predictions](test-regression-retrieval/predictions.csv),
[all raw test responses](test-regression-retrieval/responses.jsonl), and
[frozen selected protocol](test-protocol.json). Each validation folder also
includes every response and prediction. The [publication manifest](publication-manifest.json)
records artifact hashes; [verification](verification.json) checks the response
records, training-only request reconstruction and unchanged original baseline.

## Method

Two candidates were fixed before validation inference in [plan.json](plan.json):

1. **Schema:** require one `classify_incident` tool call selecting integer IDs
   from the training-derived category vocabulary. The prompt includes each
   category's eight most frequent fine labels from training as taxonomy guidance.
2. **Retrieval:** the same schema and guidance, plus four similar training reports
   and their category labels. A TF-IDF index fits only the original training text;
   target text is used only as the search query. Exact normalized target text and
   duplicate normalized training examples are excluded per query. No target labels
   or target metadata enter inference or retrieval.

Both use the same Nova Lite model in us-east-1, full target text without
truncation, temperature 0, a 256-token response limit, and four concurrent calls.
Training excerpts are limited to 2,200 source characters (head and tail, with a
truncation marker). Taxonomy guidance and example labels come only from training.
Selection of integer IDs is translated to exact category names; this is declared
before the run and does not repair free-form labels after scoring.

Each candidate runs once on **all 565 published validation reports**. The winner
is the highest unrounded official ST1 score; ties prefer fewer invalid/error
outputs, then the schema candidate. Its test protocol is frozen before one run
on **all 997 test reports**. The original scorer and invalid-output policy remain
unchanged. Wrong answers and malformed outputs are not retried; infrastructure
retries, if any, stay in the attempt record.

This development was motivated by inspecting the first test result, including
invalid category names. Therefore the new test measurement is a **regression
comparison after test exposure**, not a fresh held-out result. Validation was
used to select between the two fixed candidates; it is not an independent final
score. Related notices may span the organizer's original splits, and underlying
model training contamination is unknown. Neither ST2 nor the pantry agent's
tool loop is evaluated here.

## Reproduce

Keep the original pinned data and dependency lock. Obtain the additional
[released validation CSV](https://github.com/food-hazard-detection-semeval-2025/food-hazard-detection-semeval-2025.github.io/blob/main/data/incidents_valid.csv)
at `outputs/semeval-st1/sources/incidents_valid.csv`. Source and implementation
hashes are checked before each run.

```powershell
uv sync --frozen --group evaluation
uv run --frozen --group evaluation python -m tools.semeval_improve run --protocol evaluation/semeval-st1-v2/validation-schema-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_improve run --protocol evaluation/semeval-st1-v2/validation-retrieval-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_improve score --protocol evaluation/semeval-st1-v2/validation-schema-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_improve score --protocol evaluation/semeval-st1-v2/validation-retrieval-protocol.json
```

The `prepare` command refuses to overwrite the frozen development plan.
`select` scores both complete validation runs and refuses to overwrite an existing
test protocol. The selected test run uses:

```powershell
uv run --frozen --group evaluation python -m tools.semeval_improve run --protocol evaluation/semeval-st1-v2/test-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_improve score --protocol evaluation/semeval-st1-v2/test-protocol.json
```

Runs resume persisted rows, including invalid/error responses, without replacing
them. An interrupted in-flight call may be repeated if no response was saved.
Per-row records contain actual model content, attempt metadata, training-example
IDs/hashes/similarities, input hash, request hash and protocol hash. The public
source CSV is required to reconstruct requests; target report text is not copied
into response records.

[Harness verification](harness-tests.json) records **127 passing tests**: 112
pantry tests, nine original benchmark tests and six improvement-harness tests.
The 18 pantry scenarios still pass. Tests use synthetic inputs and stubbed
responses; the benchmark measurements require separate live model calls.

## Sources and licensing

- [Official SemEval task, dataset and scoring function](https://food-hazard-detection-semeval-2025.github.io/).
- [AWS Nova forced tool-choice documentation](https://docs.aws.amazon.com/nova/latest/userguide/tool-choice.html).
- [Dataset attribution and CC BY-NC-SA 4.0 terms](../semeval-st1/DATA-LICENSE.md),
  separately from the project code license. The training-derived fine-label
  vocabulary, example selection metadata and any redistributed dataset-derived
  materials retain this attribution and applicable terms. No organizer endorsement
  or official leaderboard rank is claimed.
