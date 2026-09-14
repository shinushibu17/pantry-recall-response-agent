# Training classifiers and category-balanced retrieval

The latest selected regression scored **0.742656 ST1**, versus **0.789229** for [v5](../semeval-st1-v5/README.md), a change of **-0.046572**. The requested **0.90 ST1 target was not reached**. This is a category-classification experiment; the deployed Strands pantry workflow is unchanged.

The selected method is a training-only, class-balanced linear SVM for product categories, combined with the recorded v5 Nova Pro hazard predictions. Selection used all 565 validation reports and the frozen unrounded ST1 rule. Exactly one selected regression was then scored on all 997 test reports. The earlier test results had already been seen; this is **repeated-validation development and an exposed-test regression**, not fresh held-out evidence or an official leaderboard score.

## Results

| Metric | v5 | Selected v6 |
| --- | ---: | ---: |
| ST1 composite | 0.789229 | 0.742656 |
| Hazard macro F1 | 0.781372 | 0.781372 |
| Product macro F1 on hazard-correct rows | 0.797086 | 0.703941 |
| Hazard accuracy | 95.59% | 95.59% |
| Product accuracy | 82.05% | 79.04% |
| Both categories correct | 78.54% | 75.63% |
| Hazard-correct rows | 953 | 953 |
| Invalid outputs / final error rows | 0 / 0 | 0 / 0 |

Hazard predictions corrected 0 previous errors and introduced 0; product predictions corrected 53 and introduced 83. Conditional product F1 can use different cohorts when hazard predictions change. All original labels, errors and denominators are retained. The remaining ST1 gap to 0.90 is 0.157344.

## Validation selection

The incumbent v5 validation score was **0.796612**. Nine candidates were frozen before their validation scores were computed. The winner was **svm-balanced-product**.

| Candidate | Validation ST1 |
| --- | ---: |
| svm-standard-both | 0.744180 |
| svm-standard-hazard | 0.763899 |
| svm-standard-product | 0.782028 |
| svm-standard-margin | 0.793318 |
| svm-balanced-both | 0.757550 |
| svm-balanced-hazard | 0.762247 |
| svm-balanced-product | 0.796713 |
| svm-balanced-margin | 0.796386 |
| pro-balanced-retrieval | 0.776712 |

The best supervised candidate improved validation by only 0.000102 over v5. That tiny difference is not evidence of a reliable generalization gain. All candidates and outcomes are preserved; no test-based candidate selection occurred within this experiment.

## What changed

- Two linear SVM classifiers learned hazard and product categories using only the 5,082 training rows. Features combine body word TFIDF 1-2grams and twice-weighted title character TFIDF 3-5grams, each capped at 80,000 features. Both standard and class-balanced weighting were tested with fixed C=1. Four fixed combinations per weighting use both heads, the hazard head, the product head, or per-head overrides at a top-two decision margin of at least 1.0. Margins are not probabilities. No threshold search was performed.
- Nova Pro received the same complete training taxonomy, four product-oriented neighbors, and up to one additional distinct nearest-body example per training hazard category. These extra examples use 900-character excerpts and are marked as category representatives, not prevalence evidence. No target annotations enter retrieval or the request. Exact normalized target bodies and duplicate training bodies are excluded per query.
- Both methods use target title and full report text. Gold labels are used only for scoring and the frozen validation decision. The scoring formula, strict Bedrock schema, infrastructure-only retry policy and original CSV hashes remain unchanged.

**Data overlap:** seven validation reports and 7 test reports have exact normalized body matches in training. The SVM is fitted on the original training split and is not decontaminated; retrieval excludes exact bodies per query. This distinction must remain in any report of the results. Underlying foundation-model training contamination is unknown.

**Cost accounting:** new Bedrock requests are recorded separately from inherited v5 predictions. The selected test phase made 0 new request attempts and reported usage {}. A zero here for a supervised/hybrid phase does not erase the cost of inherited Nova Pro predictions. All live v6 calls and retries are included in [verification](verification.json). Service token counts are not a billing statement.

## Reproduction and evidence

[Protocol metadata clarifications](PROTOCOL-NOTES.md) correct inherited descriptive fields: the balanced retriever uses training hazard labels, and supervised variants do not make new Bedrock calls. The original frozen files remain unchanged.

[150 tests pass](harness-tests.json), including five new checks for training/target separation, rare-category retrieval, duplicate exclusion, hybrid policies and selection. [Verification](verification.json) refits both training-only classifiers, checks all stored decision scores, reconstructs live retrieval requests, re-parses raw responses, recomputes every ST1 score and verifies 105 earlier published artifacts unchanged. This is builder verification, not independent certification.

- [Frozen plan](plan.json), [selection](decision.json), [test protocol](test-protocol.json), [comparison](comparison.json).
- Selected test: [results](test-regression-svm-balanced-product/results.json), [predictions](test-regression-svm-balanced-product/predictions.csv), [raw records](test-regression-svm-balanced-product/responses.jsonl), [run times](test-regression-svm-balanced-product/run.json).
- Every candidate directory contains validation results, predictions, raw records, run metadata and per-row hashes. Supervised decision traces are also included at this directory's root.
- [Publication manifest](publication-manifest.json) binds the evidence package. Historical v1-v5 archives and source CSVs were not edited.
- Implementation: [semeval_hybrid.py](../../tools/semeval_hybrid.py), [tests](../../tests/test_semeval_hybrid.py). Dependencies remain pinned in `uv.lock`.

```powershell
uv run --frozen --group evaluation python -m unittest discover -s tests
uv run --frozen --group evaluation python -m tools.semeval_hybrid score --protocol evaluation/semeval-st1-v6/test-protocol.json
```

The score command expects ignored local per-row output files from the run. Portable predictions and raw records are included here for independent rescoring against the pinned dataset. Archived protocols reject changed source/code hashes; `prepare` refuses to overwrite this experiment. Live reruns require AWS access and incur new usage. The evaluation data and derived artifacts retain [CC BY-NC-SA 4.0 attribution](../semeval-st1/DATA-LICENSE.md), separately from the project code license.
