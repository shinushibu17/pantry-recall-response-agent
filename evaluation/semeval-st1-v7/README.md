# ST1 v7: evidence-first output and Nova 2 reasoning

Neither candidate improved on v5 validation. **No new test run was selected or
executed.** The best completed observed test result remains
[v5: 0.7892287630466199](../semeval-st1-v5/README.md).

| Candidate | Validation reports | Official ST1 | Invalid / error rows |
| --- | ---: | ---: | ---: |
| Nova Pro, evidence descriptions before category IDs | 565 | 0.7871912388601794 | 0 / 0 |
| Nova 2 Lite, low reasoning, same descriptions | 565 | 0.7682939738609866 | 0 / 0 |
| Incumbent v5 Nova Pro | 565 | 0.7966116136945308 | 0 / 0 |

The [plan](plan.json) and two protocols were frozen before inference. The rule
required a gain of at least 0.005 over the incumbent validation composite before
one selected 997-report test regression could run. The [decision](decision.json)
records that the requirement was not met. Validation scores are not test scores.

Both candidates retained v5's full training-derived taxonomy, target title and
complete report text, and four training-only retrieval examples. The changed
output required short product and hazard descriptions before the two category
IDs. These are generated descriptions, not verified source quotations. Nova 2
used Bedrock's low extended-reasoning setting. The strict parser rejected extra
fields, absent descriptions and invalid IDs; no content retries or gold-label
repairs were allowed. Infrastructure failures could be retried up to three times.

The Nova Pro run used 795 attempts, including 230 throttled attempts; Nova 2 used
567 attempts, including two unavailable responses. All 1,130 final outputs were
valid. Per-run results retain reported token usage and original response content,
including any provider-redacted reasoning blocks.

- [Nova Pro protocol](validation-pro-evidence-protocol.json),
  [results](validation-pro-evidence/results.json),
  [predictions](validation-pro-evidence/predictions.csv),
  [raw records](validation-pro-evidence/responses.jsonl).
- [Nova 2 protocol](validation-nova2-low-evidence-protocol.json),
  [results](validation-nova2-low-evidence/results.json),
  [predictions](validation-nova2-low-evidence/predictions.csv),
  [raw records](validation-nova2-low-evidence/responses.jsonl).
- [Verification](verification.json) reconstructs all 1,130 requests without
  target annotations, re-parses responses, reproduces both scores and verifies
  175 earlier manifested artifacts are unchanged.
- [Test report](harness-tests.json): 155 local tests passed at this revision.
- [Publication manifest](publication-manifest.json) binds this archived package.

This is repeated-validation development after earlier test exposure. Seven
validation and seven test reports have exact normalized body matches in the
original training split; retrieval excludes exact target bodies per query.
Foundation-model training contamination is unknown. Labels and split membership
were not changed. The conditional-product component is evaluated only where
hazard predictions are correct, so ST1 is not accuracy. ST2 was not evaluated.
See the [data attribution and license](../semeval-st1/DATA-LICENSE.md).

Reproduce the saved scores after acquiring the pinned sources and restoring the
per-row records from each `responses.jsonl` into its corresponding local output
directory:

```sh
uv run --frozen --group evaluation python -m tools.semeval_evidence score --protocol evaluation/semeval-st1-v7/validation-pro-evidence-protocol.json
uv run --frozen --group evaluation python -m tools.semeval_evidence score --protocol evaluation/semeval-st1-v7/validation-nova2-low-evidence-protocol.json
```

The application remains the Nova Lite Strands workflow. These classification
experiments do not measure or modify pantry scope matching or human confirmation.
