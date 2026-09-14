# Evaluation results

The deployed pantry workflow and the SemEval classifier are separate evaluations.
The application now uses Nova Pro with pantry-specific context guidance.
The benchmark informed that choice; separate workflow checks govern deployment.

## Pantry workflow

- **165 tests pass:** 118 pantry tests and 47 benchmark harness tests.
- **18/18 frozen scenarios:** eight Pearl Milling and ten Jif stock groups.
- **Four recorded public workflow stages completed**, with eight comparisons per
  stage, two simulated human hold receipts and zero agent confirmations.

Two four-stage local Nova Pro replays passed after tool-use settings and a
bounded recovery allowance were adjusted. Earlier model-output and call-limit
failures remain preserved. These few checks do not establish a reliability or
latency improvement. The deployed Nova Pro replay subsequently passed all
four public stages, with eight comparisons each and zero agent confirmations.

[Agent evidence](../docs/submission/EVIDENCE.md) includes the original Jif
coverage failure and the later citation-failure recovery.

## SemEval ST1

| Experiment | Completed test ST1 |
| --- | ---: |
| Nova Lite baseline | 0.566941 |
| Category IDs and training retrieval | 0.679364 |
| Title-aware retrieval | 0.735795 |
| Nova Pro | 0.765878 |
| Nova Pro with full training taxonomy | **0.789229** |
| Supervised product-head hybrid | 0.742656 |

Each test run used all 997 released reports. ST1 averages hazard macro F1 and
product macro F1 on hazard-correct rows; it is not accuracy. For the best run,
those components were 0.781372 and 0.797086. All 997 outputs were valid.

The later Nova Pro/DeepSeek combination reached **0.807327 on validation**;
no test run followed because the frozen launch deadline had passed. The 0.90
stretch target was not reached. Earlier test results informed development, so
these are exposed-test regressions. Seven validation and seven test reports
match training bodies; possible foundation-model contamination is unknown.
ST2 and real-world pantry outcomes were not evaluated.

## Full evidence archive

[Download all experiment evidence](https://github.com/shinushibu17/pantry-recall-response-agent/releases/tag/benchmark-evidence-2026-09-14).
The release preserves all eight experiments, including failures, frozen
protocols, predictions, raw responses, manifests and pinned public dataset
sources. [archive.json](archive.json) records the ZIP checksum and source commit.
The matching source revision is available from the release tag.

To restore the original paths, download the ZIP to `outputs/` and extract it
from the repository root:

```powershell
Expand-Archive -LiteralPath outputs/semeval-st1-evidence-2026-09-14.zip -DestinationPath .
```

The extracted `evaluation/RESTORE.md` and experiment READMEs explain rescoring.
Verify the ZIP against the release's `.sha256` file before extraction. Restored
archives are ignored by Git; the application and unit tests need no archive or
AWS calls. [Dataset attribution and terms](DATA-LICENSE.md) apply separately
from the code license.
