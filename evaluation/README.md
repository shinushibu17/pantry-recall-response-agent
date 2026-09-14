# Evaluation results at the submission freeze

**Best completed ST1 composite: 0.789229 on all 997 released
test reports. The 0.90 target was not reached.** This is a separate model
classification benchmark, not accuracy or a measurement of the deployed
PantryRecall agent workflow.

The user set a September 14, 2026 **5 p.m. Eastern / 21:00 UTC** experiment
cutoff and asked to retain the best completed result. V5 remains that result.
The final experiment's frozen 4:40 p.m. test-launch deadline prevented a late
test run; subsequent validation results are preserved separately.

| Experiment | Main change | Completed 997-report test ST1 |
| --- | --- | ---: |
| [v1](semeval-st1/README.md) | Nova Lite, full body, zero-shot baseline | 0.566941 |
| [v2](semeval-st1-v2/README.md) | Typed category IDs and training retrieval | 0.679364 |
| [v3](semeval-st1-v3/README.md) | Title plus full text, title-weighted retrieval | 0.735795 |
| [v4](semeval-st1-v4/README.md) | Nova Pro, otherwise same inputs | 0.765878 |
| **[v5](semeval-st1-v5/README.md)** | **Full training-derived taxonomy and title/body guidance** | **0.789229** |
| [v6](semeval-st1-v6/README.md) | Validation-selected supervised product head, archived v5 hazard head | 0.742656 |
| [v7](semeval-st1-v7/README.md) | Evidence descriptions, Nova Pro vs Nova 2 low reasoning | No test: validation gain not met |
| [v8](semeval-st1-v8/README.md) | DeepSeek / Qwen / v5 category combinations | No test: frozen gain/time rule |

V5's hazard macro F1 is **0.781372** and its product macro F1
on hazard-correct rows is **0.797086**.
Their mean is ST1. Hazard accuracy is **95.59%**,
product accuracy **82.05%**, and joint accuracy
**78.54%**. All 997 final outputs are valid; 145 throttled
attempts were retried. Raw attempts and usage are preserved. These quantities
must not be presented interchangeably as “accuracy.”

Later complexity did not consistently help. V6's validation gain was only
0.000102, then test ST1 fell by 0.046572. V7's two validation scores were
0.787191 and 0.768294, below the incumbent's 0.796612. V8 direct validation scores
were DeepSeek **0.796325** and Qwen
**0.733694**; all fixed combinations are archived with their
actual selection outcome. The best combination, v5's hazard head plus DeepSeek's
product head, reached **0.807327 on validation**, but it finished after the
test-launch cutoff and has no test result. It does not replace v5's completed
test score. No partial run is presented as a complete result.

## What these results establish

Every experiment retains frozen protocols, predictions, raw responses, strict
invalid-output handling and verification records. Training labels build the
taxonomy and examples; target category annotations are absent from model
requests. No evaluation labels, split membership or denominators were changed.
The original 41 invalid baseline outputs and subsequent negative results remain
available. Individual READMEs document reproducibility and token usage.

These are repeated comparisons on an **already exposed test set**. Retaining
the best observed test result further limits unbiased generalization claims.
Seven validation and seven test reports have exact normalized body matches in
training. Retrieval excludes exact target bodies per query; the v6 supervised
models use the original training split. Foundation-model training contamination
is unknown. ST2 was not evaluated and no leaderboard rank is claimed.

The [published task and scoring definition](https://food-hazard-detection-semeval-2025.github.io/)
use hazard macro F1 and conditional product macro F1. Rare categories therefore
matter even when overall accuracy is high. See the [dataset attribution and
license](semeval-st1/DATA-LICENSE.md); its terms are separate from the project's
Apache-2.0 source-code license.

## Pantry workflow checks are separate

The deployed Nova Lite Strands agent uses reviewed historical recalls and
synthetic inventory. It has **112 pantry tests and 18 frozen scope cases**,
plus recorded public workflow checks. The combined local suite, including all
eight benchmark harnesses, has **159 passing tests** (112 + 47), with no failures,
errors or skips. See [the test record](semeval-st1-v8/harness-tests.json) and
[the portable pantry evidence](../docs/submission/EVIDENCE.md).

Independent expectation review, an untouched recall evaluation and a volunteer
pilot remain future validation. The prototype does not establish field accuracy,
physical action completion or general food safety.
