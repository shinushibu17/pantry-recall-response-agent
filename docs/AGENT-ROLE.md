# Agent role and event-triggered follow-ups

One Strands agent on Amazon Bedrock chooses useful next checks for the fictional
pantry. Reviewed recall scope and deterministic task transitions remain the
authority for identification and physical-action quantities.

## What the model chooses

The web agent has seven tools: `load_recall_fixture`, `load_inventory`,
`find_candidates`, `compare_scope`, `get_work_queue`, `get_case_history`, and
`submit_briefing`. It must compare every stock group, including non-candidates.
It discovers accepted changes and OPEN tasks, chooses additional histories to
read, then proposes up to three existing task IDs in its own order with a short
advisory rationale. The application attaches each task's stored evidence references.

The host requires histories for all changed stock groups and an open next step
for at least one changed group when available. It checks every selected task's
current binding. Task facts, location, quantity, instructions and the complete
evidence-reference list are copied from storage. The model's rationale is unverified;
evidence membership does not prove that every sentence in that rationale is
supported. Priority is not a food-safety risk ranking.

After a two-box hold receipt the canonical remaining quantity is two. After the
second receipt, the completed task becomes ineligible; the agent reads its
history and chooses other OPEN work. No model tool supplies label observations,
confirms a hold, releases food or changes the pinned source.

## Follow-up lifecycle

The first manual start enables automatic follow-ups for that visitor. Accepted
`EVIDENCE_ADDED` and `HOLD_CONFIRMED` events trigger a new run. Exact command replays
and rejected writes do not trigger inference. Simultaneous updates coalesce;
stale or incomplete briefings are withheld. Only one agent runs across visitors,
with the existing persisted 20-starts-per-UTC-day allowance.

Control state and event cursors persist in SQLite. Pending work is considered on
startup, accepted writes, job completion and status reads. A failed attempt is
retained and does not retry forever. Quota/concurrency limits leave accepted
evidence and receipts intact and show a queued status. Pause stops future
automatic starts. Reset pauses the old replay, creates a new visitor replay and
keeps the old audit. There is no background recall-feed monitoring.

## Verification

Local live verification passed on September 13, 2026 at 18:23:28 UTC. The full
112-test suite and JavaScript syntax check also passed after the citation-binding fix. One earlier suite run
had a Windows socket abort in the authentication HTTP test; its focused rerun
and the subsequent complete suite passed without a code change. The failed log
is preserved in `outputs/investigation-preview/tests-final.txt`.

`outputs/investigation-preview/live-check-4/verification.json` preserves four
COMPLETE live briefings, eight comparisons each, two explicit synthetic human
receipts, and zero agent confirmations:

| Scene | Model calls | Tool calls | Seconds | Agent-selected stock |
| --- | --- | --- | --- | --- |
| Initial | 5 | 9 | 8.45 | affected, missing_code, excluded_code |
| Evidence arrives | 6 | 9 | 10.79 | missing_code, ambiguous_code, contradictory_label |
| Two boxes held | 7 | 10 | 13.68 | affected, missing_code, excluded_code |
| Hold completed | 9 | 12 | 14.43 | affected, excluded_code, mixed_codes |

A separate local browser check completed an initial briefing (8 comparisons,
9 tool calls, 6 model calls), then an automatic evidence-triggered briefing
(8 comparisons, 10 tool calls, 7 model calls). It displayed the exact missing-code
change, a four-box open hold, and functioning pause control. These observations
establish behavior on this replay, not reliability across arbitrary notices.

Each verification attempt uses a fresh output directory:

```sh
uv run --frozen python -m tools.verify_investigation --url http://127.0.0.1:8082 --output outputs/investigation-preview/new-check
```

The verifier preserves each response before asserting COMPLETE, eight executed
comparisons and a current validated briefing. It checks manual start, evidence
arrival, a two-box partial hold, exact replay, and final completion selecting
other open work. It pauses follow-ups afterward.

Preserved development failures:

- `live-check-1`: expired local AWS login; no successful briefing.
- `live-check-2`: initial briefing completed; the evidence follow-up failed with
  Bedrock `ModelErrorException` (invalid tool-use sequence).
- `live-check-3`: initial briefing completed; the evidence follow-up exhausted
  its bounded call budget while correcting a rejected plan. Partial execution
  and the failure code were retained. Validation feedback was then changed to
  report all problems together with exact missing IDs and allowed evidence.

These are development runs, not held-out evaluations. Original Pearl/Jif source
locks, expectations and the first failed Jif check remain unchanged. The existing
terminal recording demonstrates the earlier five-tool baseline; it does not
demonstrate the new automatic investigation loop.

The updated AWS deployment passed the same four-stage verification at 18:31 UTC:
`outputs/deployment/investigation-check-1/verification.json`. All four briefings
completed eight comparisons, taking 9.42–11.53 seconds and 5–7 model calls each.
After the final receipt it selected `excluded_code`, `similar_product`, and
`mixed_codes`; the completed hold stayed closed. The 13 checks in
`outputs/deployment/agent-role-boundary-check/verification.json` also passed,
including visitor isolation, replay and history/receipt persistence across an
actual service restart. Both verification replays contain only synthetic data.

## Citation-loop regression

A subsequent public browser run completed eight comparisons but failed after
12 model calls and 16 tool calls. The retained trace shows repeated submissions
of the same three valid task IDs with `#best_by_manufacturing_code` citation
suffixes that were not members of those tasks' evidence references. The model
read the requested histories but kept resubmitting those rejected citations.

The fix removes `evidence_ids` from the model's submission schema. It chooses
task IDs and reasons; the host binds all evidence references from those exact
current OPEN tasks. The original evidence validator still rejects the bad
citations. No reference is fuzzy-matched, repaired, or treated as supporting
arbitrary model prose. The UI shows the complete stored task evidence list and
still labels the rationale advisory. Two new regressions cover the failed
browser's three selections and rejection of an unknown task ID. Earlier failed
reports remain intact, and the 12-model-call/20-tool-call bounds are unchanged.

Post-fix verification on September 13 passed all 112 tests and JavaScript syntax
checks. Both four-stage live replays passed: local evidence is in
`outputs/investigation-preview/citation-fix-check/verification.json`; public AWS
evidence is in `outputs/deployment/citation-fix-check/verification.json`. Each
stage executed eight comparisons and retained the selected tasks' exact stored
evidence lists. Public runs used 4–7 model calls and took 7.22–13.02 seconds.

The same public browser session that previously failed was rerun without resetting
its pantry. It completed eight comparisons, ten tool calls and six model calls.
The expanded exclusion task showed the authored review policy, original product
table, explicit other-products bounding sentence, source hash and inventory
reference. The original failed run remains stored. This verifies the specific
citation-loop fix on the controlled replay; it is not a guarantee that a model
request can never fail.
