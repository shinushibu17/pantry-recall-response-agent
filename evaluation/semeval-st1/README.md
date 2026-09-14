# SemEval 2025 Task 9 — separate ST1 classification evaluation

**Completed September 14, 2026:** all 997 test reports processed in one frozen
run. The published ST1 scoring function gives **0.566941** under the disclosed
invalid-output policy. The combined local suite also passes 121 tests (112 pantry
tests plus nine benchmark harness tests) and the 18 pantry scope scenarios.

This page preserves the initial baseline. A later
[validation-selected regression comparison](../semeval-st1-v2/README.md)
scored 0.679364 with zero invalid outputs; its candidate selection and test-exposure
limits are documented separately. The original results below are unchanged.

This evaluates Amazon Nova Lite's product-category and hazard-category
classification. It does not invoke the deployed Strands investigation loop or
evaluate lot matching, pantry task selection, source-citation correctness,
physical-action confirmation, or ST2 exact product/hazard labels.

## Results

| Measure | Result |
| --- | --- |
| Released test reports processed / scored | 997 / 997 |
| ST1 composite score | **0.566941** |
| Hazard macro-F1 | 0.463246 |
| Product macro-F1 on hazard-correct rows | 0.670635 |
| Hazard accuracy, additional diagnostic | 84.55% |
| Product accuracy, additional diagnostic | 66.30% |
| Joint accuracy, additional diagnostic | 57.87% |
| Valid outputs / invalid outputs / API error rows | 956 / 41 / 0 |
| Model attempts | 997; no retries occurred |
| Response-reported input / output tokens | 899,281 / 29,112 |
| Execution window | 16:30:08–16:32:23 UTC, September 14; four concurrent requests |

The ST1 score is not an accuracy percentage. All 41 invalid responses emitted
product labels outside the frozen vocabulary. The most frequent was
`sauces and condiments` (22 responses), rather than the allowed
`soups, broths, sauces and condiments`. Per the frozen rule, either invalid field
invalidates the entire response, and both fields receive the sentinel for scoring.
No post-hoc label mapping or improved replacement score was substituted.

Performance varies substantially by category. Hazard F1 was 0.9393 for allergens
(365 test rows) and 0.9152 for biological hazards (343), but 0.2727 for fraud
(75) and 0 for other hazard (26). Migration also scored 0 but has only one test
row, so its estimate is particularly unstable. These results expose limitations
of this zero-shot model/prompt baseline; they do not establish reliable automated
scope extraction or validate the pantry agent as a whole.

Portable records: [results and per-category metrics](results.json),
[predictions](predictions.csv), [all raw responses and attempts](responses.jsonl),
[execution times](run.json), [error analysis](error-analysis.json),
[harness test verification](harness-tests.json), and
[publication hashes](publication-manifest.json). Original per-row files are also
hashed in [record-manifest.json](record-manifest.json). No test-row text is copied
into the public response archive; input hashes bind rows to the pinned CSV.

## Frozen experiment

- All **997 released test rows**, original CSV order, no subset or exclusions.
- **Full text only**, without truncation or title fallback. No test labels or
  metadata are included in inference requests.
- The allowed labels are the **10 hazard categories and 22 product categories**
  found in the training split. Training texts are not used as examples.
- One zero-shot prompt, no test-label feedback or prompt tuning. Initial test
  rows were visible during source/schema verification; this is not a claim that
  the operator or underlying model has never encountered the public data.
- Bedrock `amazon.nova-lite-v1:0`, `us-east-1`, temperature 0, maximum 128 output
  tokens, four concurrent requests. Temperature 0 does not guarantee identical
  outputs across future service calls.
- Up to three attempts for transport/throttling/service errors only. Malformed
  outputs and wrong predictions are not retried. Every completed row persists;
  resuming reuses it. An interrupted in-flight call without a saved response may
  be repeated and can have unreported usage.
- Invalid/error outputs remain in the denominator using an explicit invalid
  label. Exact labels are required; there is no fuzzy repair. Removing a sole
  JSON code fence is the only formatting accommodation.

[protocol.json](protocol.json) freezes membership, prompt, input rules, model
settings, source hashes, implementation hash and dependency-lock hash before
benchmark inference. Changing that implementation or lock requires a new,
explicitly versioned experiment; do not overwrite the original protocol.

## Scoring

The harness uses the organizer's published `compute_score` calculation: average
hazard macro-F1 with product macro-F1 computed **only on hazard-correct rows**.
Ordinary product F1 across every row is reported separately as a diagnostic.
If no hazard prediction is correct, the conditional score is undefined and
reported as null. Invalid labels participate in the scorer's default label union;
their counts and the sentinel policy are disclosed. No official leaderboard
submission or ranking is claimed. See the [official task and scorer](https://food-hazard-detection-semeval-2025.github.io/).

The scorer refuses a full-test result when any row lacks a record. Execution
completion is separate from prediction quality; a COMPLETE run can contain
wrong predictions or failed requests. No threshold has been chosen after seeing
answers.

## Run or resume

From the repository root, use the locked evaluation dependency group:

```powershell
uv sync --frozen --group evaluation
aws login --profile pantry-recall --region us-east-1
uv run --frozen --group evaluation python -m pantry_recall.aws_access --profile pantry-recall --region us-east-1 --output outputs/semeval-access.json
uv run --frozen --group evaluation python -m tools.semeval_eval run
uv run --frozen --group evaluation python -m tools.semeval_eval score
```

The existing local protocol is already frozen; do not rerun `prepare` over it.
`run` uses `outputs/semeval-st1/run-1/` by default. Saved rows are reused, including
invalid/error results. After correcting an access issue, resuming can process
remaining rows but does not erase prior failed rows. A new comparison experiment
must use another `--run-dir` and retain the original run.

Artifacts include one `row-<id>.json` per test row with raw model output, usage,
request IDs, all attempts, input hash and protocol binding; `run.json` records
execution times. Scoring writes `results.json`, `predictions.csv` and
`record-manifest.json`. The model's raw text is evaluation data, never an
instruction to the reader. Token totals are response-reported usage, not an AWS
billing statement.

For a new checkout, download the source files into the ignored directory first:

```powershell
New-Item -ItemType Directory -Force outputs/semeval-st1/sources | Out-Null
Invoke-WebRequest https://raw.githubusercontent.com/food-hazard-detection-semeval-2025/food-hazard-detection-semeval-2025.github.io/main/data/incidents_train.csv -OutFile outputs/semeval-st1/sources/incidents_train.csv
Invoke-WebRequest https://raw.githubusercontent.com/food-hazard-detection-semeval-2025/food-hazard-detection-semeval-2025.github.io/main/data/incidents_test.csv -OutFile outputs/semeval-st1/sources/incidents_test.csv
Invoke-WebRequest https://food-hazard-detection-semeval-2025.github.io/ -OutFile outputs/semeval-st1/sources/task.html
```

The runner checks every file against the pinned hash. Upstream changes will
produce an explicit mismatch rather than silently changing the experiment.
The original local files are preserved for the current run. To create a new
protocol from intentionally reviewed new sources, use a separate checkout or
versioned experiment directory; retain this protocol and its results.

Run the combined tests with:

```sh
uv run --frozen --group evaluation python -m pantry_recall.evaluate --tests
```

## Attribution and scope of the evidence

Dataset: **SemEval 2025 Task 9: The Food Hazard Detection Challenge**, by its
organizers and contributors, with annotations credited by the task page to
Agroknow experts. Sources: [task page](https://food-hazard-detection-semeval-2025.github.io/),
[released training CSV](https://github.com/food-hazard-detection-semeval-2025/food-hazard-detection-semeval-2025.github.io/blob/main/data/incidents_train.csv),
and [released test CSV](https://github.com/food-hazard-detection-semeval-2025/food-hazard-detection-semeval-2025.github.io/blob/main/data/incidents_test.csv).

The dataset is published under **CC BY-NC-SA 4.0**, separately from this project's
Apache-2.0 code license. See [DATA-LICENSE.md](DATA-LICENSE.md). Original CSVs are
kept in ignored local outputs; the training-derived vocabulary in the protocol
retains the dataset attribution and terms. No row text has been edited. Prompt
wrapping and prediction parsing are the disclosed evaluation adaptations.

This supplementary model baseline cannot establish generalization of the pantry
workflow. Public test data may have appeared in model training; contamination is
unknown. Keep these metrics separate from the 18 source-grounded inventory
scenarios and from the original first Jif agent evaluation.
