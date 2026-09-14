# Verification evidence

These are prototype checks using synthetic stock and actions, not independent
certification or measured pantry outcomes.

| Check | Result | Evidence |
| --- | --- | --- |
| Current automated suite | 159 tests pass: 112 pantry and 47 benchmark tests | [Test command](../../README.md#evaluation-results); archived harness report in the [benchmark release](../../evaluation/README.md#full-evidence-archive) |
| Frozen scope cases | Pearl 8/8; Jif 10/10 | [Offline report](evidence/offline-evaluation.json), [Pearl review](../../fixtures/pearl_milling_2025/REVIEW.md), [Jif review](../../fixtures/jif_2022/REVIEW.md) |
| Public workflow | Four COMPLETE briefings; two human receipts; zero agent confirmations | [Workflow report](evidence/public-workflow.json) |
| Citation failure recovery | Same browser session completed without resetting its pantry | [Recovery report](evidence/browser-recovery.json) |
| Deployment boundaries | 13 checks passed, including isolation and persistence across restart | [Boundary report](evidence/public-boundaries.json) |
| First Jif run | INCOMPLETE_TOOL_COVERAGE; 0/10 comparisons executed | [Original failure](../../evaluation/jif-first-run/README.md) |

## What evaluation changed

The skipped Jif comparisons prompted a bounded continuation for missing tool
work. Forced SDK tests cover that branch; the later live Jif pass completed
10/10 comparisons without needing it. That pass alone does not establish a
causal reliability improvement.

A browser run repeatedly invented citation identifiers. The briefing interface
now accepts existing task IDs and reasons, while the application attaches exact
stored evidence. The same previously failing session completed, followed by a
successful four-stage public check. Original failed reports remain preserved.

## Public workflow trace

Recorded on September 13, 2026 through the deployed app and Bedrock. Future
model choices and timings can differ.

| Trigger | Comparisons | Model / tool calls | Duration | Trace |
| --- | ---: | ---: | ---: | --- |
| Initial start | 8 | 6 / 10 | 10.11 s | [Initial](evidence/public-initial.json) |
| Matching label evidence | 8 | 4 / 11 | 7.22 s | [After evidence](evidence/public-after-evidence.json) |
| First two-box receipt | 8 | 7 / 11 | 10.16 s | [Partial hold](evidence/public-partial-hold.json) |
| Remaining two-box receipt | 8 | 7 / 12 | 13.02 s | [Completed hold](evidence/public-completed-hold.json) |

## Separate classification benchmark

Best completed SemEval ST1 test composite: **0.789229** on 997 reports. The later
**0.807327** result is validation-only. Those experiments did not change the
Nova Lite pantry agent. [Results and the downloadable archive](../../evaluation/README.md)
preserve all candidates, raw responses, protocols, failures and limitations.

## Interpretation and integrity

Jif's first run was held out from agent prompt tuning, not adapter development;
later runs are regressions after feedback. Expected outcomes were source-reviewed
and frozen before the corresponding matchers, but independent sign-off remains
pending. No untouched recall evaluation, pantry pilot or measured time saving
has been completed. Confirmations are human assertions, not verified physical
handling. Advisory model reasoning is not independently validated.

[manifest.json](evidence/manifest.json) binds the portable workflow records and
records their provenance. The offline report contains the 112-test pantry suite
at its original packaging time; the current 159 includes benchmark tests.
Live records keep their original timestamps. A hash establishes content
integrity, not independent verification or universal service availability.
