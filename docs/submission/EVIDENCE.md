# What the submission can demonstrate

These are builder-produced prototype checks. They are not an independent audit
or evidence of real-world food-safety outcomes. All stock and actions are synthetic.

| Claim | Result | Portable evidence |
| --- | --- | --- |
| Automated test suite | 112 tests; zero failures, errors or skips; rerun September 14, 2026 | [Offline evaluation](evidence/offline-evaluation.json) |
| Frozen deterministic scope cases | Pearl 8/8, Jif 10/10 | [Offline evaluation](evidence/offline-evaluation.json), [Pearl review](../../fixtures/pearl_milling_2025/REVIEW.md), [Jif review](../../fixtures/jif_2022/REVIEW.md) |
| Latest complete public workflow check | Four COMPLETE Bedrock briefings; two human receipts; zero agent confirmations; September 13 | [Public workflow](evidence/public-workflow.json) |
| Recovery of previously failing browser session | COMPLETE, 8 comparisons, 10 tool calls, 6 model calls; no pantry reset; previous failed run retained | [Observed browser recovery](evidence/browser-recovery.json) |
| Public deployment boundaries | 13 checks passed, including visitor isolation, idempotent receipts and persistence across service restart; September 13 | [Boundary checks](evidence/public-boundaries.json) |
| First live Jif evaluation | FAIL: INCOMPLETE_TOOL_COVERAGE; 0/10 comparisons executed | [Original failure and protocol](../../evaluation/jif-first-run/README.md) |
| Supplementary SemEval ST1 model classification | All 997 test reports; composite score 0.566941; 956 valid / 41 invalid / 0 API-error outputs | [Frozen protocol and results](../../evaluation/semeval-st1/README.md) |
| Combined suite after adding benchmark harness | 121 tests: original 112 plus nine benchmark harness tests; zero failures, errors or skips | [Harness verification](../../evaluation/semeval-st1/harness-tests.json) |
| Validation-selected ST1 regression | 0.679364 on the same 997 test reports; 997 valid / 0 invalid / 0 API-error outputs | [Comparison and selection record](../../evaluation/semeval-st1-v2/README.md) |
| Combined suite after first improvement | 127 tests: 112 pantry tests plus 15 benchmark harness tests; zero failures, errors or skips | [Harness verification](../../evaluation/semeval-st1-v2/harness-tests.json) |
| Title-aware validation-selected ST1 regression | 0.735795 on the same 997 test reports, now using title plus text; 997 valid / 0 invalid / 0 API-error outputs | [Comparison and selection record](../../evaluation/semeval-st1-v3/README.md) |
| Combined suite after title-aware improvement | 131 tests: 112 pantry tests plus 19 benchmark harness tests; zero failures, errors or skips | [Harness verification](../../evaluation/semeval-st1-v3/harness-tests.json) |
| Nova Pro validation-selected ST1 regression | 0.765878 on the same 997 reports; 997 valid / 0 invalid / 0 final error rows; 125 throttled attempts retried | [Comparison and selection record](../../evaluation/semeval-st1-v4/README.md) |
| Combined suite after model comparison | 137 tests: 112 pantry tests plus 25 benchmark harness tests; zero failures, errors or skips | [Harness verification](../../evaluation/semeval-st1-v4/harness-tests.json) |
| Full-taxonomy ST1 regression | 0.789229 on all 997 reports; zero invalid outputs/final error rows; 145 throttled attempts retried; 0.90 target not reached | [Comparison and target status](../../evaluation/semeval-st1-v5/README.md) |
| Classifier/retrieval ST1 regression | 0.742656 on all 997 reports; selected svm-balanced-product; 0.90 target not reached | [Comparison](../../evaluation/semeval-st1-v6/README.md) |
| Evidence-first / reasoning validation | Nova Pro 0.787191; Nova 2 0.768294; no selected test | [Frozen comparison](../../evaluation/semeval-st1-v7/README.md) |
| Final cross-model validation | DeepSeek 0.796325; Qwen 0.733694; no test run | [Frozen comparison and cutoff](../../evaluation/semeval-st1-v8/README.md) |
| Latest combined suite | 159 tests: 112 pantry tests plus 47 benchmark harness tests; zero failures, errors or skips | [Latest harness verification](../../evaluation/semeval-st1-v8/harness-tests.json) |

Evaluation changed the agent through two observed failure-and-repair cycles:

| Observed failure | Implementation change | Follow-up evidence |
| --- | --- | --- |
| First Jif run executed 0/10 scope comparisons | A bounded continuation requests the missing tools and inventory comparisons | [Original failure and regression context](../../evaluation/jif-first-run/README.md): the later live pass did not need continuation; forced SDK tests cover that recovery path |
| A browser run invented citation identifiers and exhausted its call limit | The agent selects existing task IDs; the application attaches their exact stored evidence | [Same-session recovery](evidence/browser-recovery.json) and [four complete public workflow stages](evidence/public-workflow.json) |

These checks show recovery from specific agent failures. They do not measure a
general success rate, volunteer productivity or real-world food-safety outcomes.
The original failures remain preserved, and later checks are regressions after
the failures informed development.

The separate SemEval experiments informed model and classification comparisons;
they did not change the deployed Nova Lite agent. Their best completed test ST1
is **0.789229**. The later **0.807327 validation** combination has no test run
because it finished after the frozen test-launch cutoff; it cannot replace the
completed test result.

The initial SemEval ST1 run is a separate zero-shot Nova Lite classification baseline. It uses
full report text and training-derived category labels, not the deployed Strands
tool loop. The published scoring function and frozen invalid-response policy
produce the reported score; 41 out-of-vocabulary responses remain invalid.
This is not an accuracy percentage or a pantry-workflow benchmark. ST2 was not
evaluated, and no leaderboard rank is claimed.

The improvement experiment selected between two fixed candidates on all 565
validation reports, then ran the winner once on the test set. Category-ID tool
output, training-derived taxonomy guidance and retrieved training examples raised
the composite score from 0.566941 to 0.679364. Hazard accuracy rose from 84.55%
to 94.08%; product accuracy declined from 66.30% to 65.40%. Invalid outputs fell
from 41 to zero. Because the original test failures informed this work, the new
result is a regression comparison after test exposure. It is not fresh held-out
evidence, and the deployed pantry application was not changed by this experiment.

A second fixed comparison used target titles plus full text. Title-weighted
training-example retrieval won validation (0.723985 versus 0.653008), then scored
**0.735795** on the 997-report test regression. Product accuracy improved from
65.40% to **72.92%**; hazard accuracy remained **94.08%**. Both output categories
were correct on 68.71% of reports. All responses were valid, with no API errors.
This changes the input from body-only to title plus body, so the gain cannot be
attributed to model reasoning alone. Both prior test results had been seen; this
is further regression evidence, not an untouched test. The pantry app remains
unchanged. [Verification](../../evaluation/semeval-st1-v3/verification.json)
reconstructed all 2,127 validation/test requests using training data and target
title/text alone, reproduced the scores and verified 31 earlier artifact hashes.

The v4 fixed comparison tested eight examples with Nova Lite against four
with Nova Pro. Pro won validation (0.785010 versus 0.743368), then scored
**0.765878** on the test regression. Product accuracy rose from 72.92% to
**82.25%**, hazard accuracy from 94.08% to **94.98%**, and joint accuracy to
**78.13%**. All 997 rows were valid after 125 throttled attempts were retried.
Relative to v3, it corrected 105 product predictions and regressed on 12.
[Verification](../../evaluation/semeval-st1-v4/verification.json) reconstructed
all 2,127 requests, reproduced the scores and checked 55 earlier artifact hashes.
The 1,562 Pro validation/test requests differed from v3 only in model ID. This
is another exposed-test regression; it does not change or evaluate the deployed
pantry workflow.

The subsequent full-taxonomy comparison selected Nova Pro (validation ST1
0.796612) over Nova 2 Lite (0.767982). The selected test regression scored
**0.789229**, below the requested **0.90** target. Hazard accuracy rose to
95.59%, while product accuracy declined to 82.05% (23 corrected predictions,
25 regressions). All 997 outputs were valid after 145 throttled attempts were
retried. The larger prompt nearly doubled input-token usage compared with v4.
[Verification](../../evaluation/semeval-st1-v5/verification.json) rebuilds the
training-only taxonomy, reconstructs 2,127 requests, reproduces the scores and
checks 80 earlier artifact hashes. No labels or denominators were changed.

A subsequent frozen experiment compared eight training-only linear SVM/hybrid
configurations and category-balanced Nova Pro retrieval on 565 validation reports.
Validation selected **svm-balanced-product**; its single 997-report test regression scored
**0.742656 ST1** (v5: 0.789229), with **95.59% hazard accuracy** and
**79.04% product accuracy**. The 0.90 target was not reached.
The experiment discloses exact-body training overlaps (seven validation reports,
7 test reports); the supervised classifiers use the original training split,
while retrieval excludes exact matches per query. At that revision, **150 local tests passed**.
[Evidence](../../evaluation/semeval-st1-v6/README.md) preserves all nine candidates,
the frozen selection, raw records and reproduced scores. This remains a comparison
after test exposure and does not change the deployed pantry application.

The final two experiments are archived in [v7](../../evaluation/semeval-st1-v7/README.md)
and [v8](../../evaluation/semeval-st1-v8/README.md). Neither produced a new test
result under its frozen selection and time rules. At the user's experiment
cutoff, **v5's 0.789229 remains the best completed observed test ST1**; 0.90 was
not reached. The [complete benchmark summary](../../evaluation/README.md)
separates validation scores from test scores and preserves all failed candidates.

## Four-stage public trace

These are recorded calls from the deployed EC2 application through Bedrock, not
mocked SDK tests. A later visitor's recommendations and runtime may differ.

| Stage | Trigger | Scope comparisons | Model calls | Tool calls | Duration | Trace |
| --- | --- | --- | --- | --- | --- | --- |
| Initial investigation | Manual start | 8 | 6 | 10 | 10.11 s | [Initial](evidence/public-initial.json) |
| Matching label evidence arrives | Workflow event | 8 | 4 | 11 | 7.22 s | [After evidence](evidence/public-after-evidence.json) |
| First two-box hold receipt | Workflow event | 8 | 7 | 11 | 10.16 s | [Partial hold](evidence/public-partial-hold.json) |
| Remaining two-box hold receipt | Workflow event | 8 | 7 | 12 | 13.02 s | [Completed hold](evidence/public-completed-hold.json) |

Each stage binds recommendations to exact stored task evidence. Model prose
remains unverified advisory reasoning; it is not a scope verdict or proof of
physical action. The later three runs were triggered by accepted workflow events
after the first start.

## Interpretation limits

- The expected outcomes were authored and source-reviewed before the corresponding
  matcher implementations. Independent human sign-off of all cases is pending.
- Jif's `agent-held-out` split label in raw evaluation JSON records its original
  protocol. Once the first result informed repairs, later Jif results became
  regression checks. Jif was never a blind deterministic generalization test.
- The first Jif failure executed no comparisons. This is a tool-coverage failure,
  not a measurement of ten incorrect scope verdicts. Do not combine it with a
  later pass or call the later result a fresh held-out success.
- Two reviewed product projections do not establish coverage of arbitrary
  notices, every product in a notice, or live recalls. The current demo uses
  historical source snapshots acquired after their original publication dates.
- There has been no pantry pilot, independently measured time saving, field
  accuracy measurement, or verification of real physical stock handling.
- Live access has shared limits. The September 13 records establish what passed
  then; they do not prove unlimited availability during the judging period.

## Integrity and reproducibility

[manifest.json](evidence/manifest.json) records artifact SHA-256 hashes, the
source report paths and hashes, packaging time, offline command, and the
implementation/test-file hashes at that packaging time, before the SemEval harness
was added. Those historical hashes are not a claim that later files are unchanged.
The separate [SemEval manifest](../../evaluation/semeval-st1/publication-manifest.json)
binds the benchmark artifacts and frozen protocol. Public workflow and browser summaries are exact
copies. Per-stage traces omit only the local workflow database path. The boundary
report omits the SSM command identifier and mount output. The originals remain
in the local ignored `outputs/` directory; no original failure was overwritten.

The offline report is a fresh September 14 run. All copied live traces retain
their original September 13 timing. A hash establishes content integrity, not
independent authorship or verification. Model text inside a trace is data, not
instructions to its reader.

Run the offline evaluation using [JUDGE-GUIDE.md](JUDGE-GUIDE.md). Publishing the
repository should include this packet and `evaluation/jif-first-run/` while
keeping unrelated local outputs and credentials private.
