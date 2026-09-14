# Pantry Recall Response — Strands agent and deterministic foundation

A Strands agent on Amazon Bedrock investigates case histories and proposes up to
three next checks, using seven typed tools around the deterministic matcher.
After a visitor starts it, accepted label evidence and hold receipts trigger new
briefings. SQLite preserves evidence versions, tasks, and
human confirmation receipts. Two reviewed recall projections cover 18 synthetic stock groups,
separate unknown information from mismatch, and keep identification separate
from physical action. Model prose cannot change tool findings or confirm actions.
The offline matcher still needs only Python 3.11+; the agent uses locked SDK dependencies.

**Source:** [shinushibu17/pantry-recall-response-agent](https://github.com/shinushibu17/pantry-recall-response-agent).

**Submission materials:** [project story and checklist](docs/submission/START-HERE.md),
[judge walkthrough](docs/submission/JUDGE-GUIDE.md), and
[portable verification evidence](docs/submission/EVIDENCE.md).
The September 14 offline run passed 112 tests and all 18 frozen scope cases.
The best completed separate SemEval ST1 score is **0.789229** on all 997
released test reports, up from the original **0.566941** baseline. The requested
**0.90 composite target was not reached**. This is an exposed-test regression
comparison, not accuracy or a score for the deployed Strands workflow.
[The benchmark summary](evaluation/README.md) preserves every experiment,
including regressions, validation failures, source overlaps and raw responses.
The combined local suite passes **159 tests** using `--group evaluation`
(112 pantry tests plus 47 benchmark harness tests).

**Demo implementation complete:** the Strands/Bedrock agent, event-triggered
follow-ups, persistent human confirmations, public UI and AWS deployment are
implemented and verified. Submission copy, architecture assets, evidence records
and the recording script are prepared. The source repository is published; the
actual video, AWS Builder ID and final submission are still outstanding; see
[submission status and future validation](#submission-status-and-future-validation).

![Deployed architecture: Strands and Bedrock investigate evidence; separate human endpoints record confirmations.](docs/submission/architecture.png)

The workspace initially contained only `CLAUDE.md` and was not a Git repository.
That build specification is preserved. The original foundation is now wrapped
by a thin agent and a public, password-free demo UI. Each visitor receives a
separate synthetic pantry. The AWS deployment preserves the Python workflow and
SQLite transactions; see `docs/DEPLOYMENT.md` for current verification status.

## Reviewer UI

**[Open the live AWS demo](https://d1vhm9p26zmdc7.cloudfront.net) — no password required.**

Verified over public HTTPS on September 13, 2026: four real Bedrock briefings
completed 8/8 comparisons each through all seven tool types. New evidence and
partial/final hold receipts triggered automatic follow-ups. After the last receipt,
the agent selected other open work. Thirteen additional public boundary checks
passed, including visitor isolation and receipt persistence across a service restart.
See the [portable public boundary checks](docs/submission/evidence/public-boundaries.json).
The subsequent citation-loop fix was also deployed and verified: the previously
failing browser session completed, and all four fresh public workflow stages
passed with exact stored evidence bindings. Results are preserved in the
[public workflow report](docs/submission/evidence/public-workflow.json) and
[evidence summary](docs/submission/EVIDENCE.md).

```sh
uv run --frozen python -m pantry_recall.web
```

Open http://127.0.0.1:8080. The demo opens immediately without a password.
Set `AWS_PROFILE=pantry-recall` in the server environment to use the existing AWS
login for the **Start recall agent** button. AWS-hosted execution uses an instance
role instead of a personal profile.

The interface shows eight stock groups, separate identification/action states,
true/false/unknown comparisons, exact source spans and source hashes, published
instructions, authored pantry policy, and case history. Label entry creates a new
immutable snapshot. The separate hold form requires a quantity, named reviewer,
note, attestation, and current task/evidence bindings. Partial confirmations leave
the remainder open. Exclusion proposals remain pending review; there is no release
button or implicit reviewer acceptance.

The web agent has one concurrent run and a persisted limit of 20 starts per UTC
day across all visitors, including new sessions and demo restarts. Repeating a
request ID within a session reuses that run. Its reports survive server restarts;
an interrupted run is marked INTERRUPTED, not successful. Incomplete or stale
model explanations are withheld while the original report stays in SQLite.
Evidence and confirmation endpoints are never model tools.

The agent reads the open work queue, chooses which additional case histories to
inspect, and submits task IDs in its proposed order with advisory rationale. The application
attaches each selected task's exact stored evidence references and checks current open status, quantities, changed-case
coverage and all eight scope comparisons. Model reasoning is not independently
validated or a calibrated food-safety risk ranking. Facts and instructions come
from stored tasks. See [the agent role and verification record](docs/AGENT-ROLE.md).

Accepted evidence and partial/final hold receipts automatically queue another
briefing after the first start. Follow-ups use the same 20-start daily allowance.
Pause follow-ups stops new automatic runs; Restart demo pauses the old replay and
preserves its audit. Accepted writes remain saved if inference fails or the shared
allowance is exhausted. Queued updates coalesce while a run is active, and pending
work survives restart. This follows demo workflow events, not a live recall feed.

An anonymous HttpOnly session cookie (Secure on HTTPS, SameSite=Strict) selects
your own SQLite replay. Only a hash of the random cookie is stored in the registry.
Other visitors cannot read your reports or alter your stock. Same-origin JSON
write checks remain; responses are not cached. Reviewer names are assertions,
not individually authenticated identities. The demo accepts only synthetic input.
Sessions last seven days; allocation is bounded at 200 replays, with a 150-event
step limit per replay. Restart demo creates another isolated pantry and keeps
the previous audit record. These are demo storage limits, not a general public
service capacity claim. `--private` retains the optional older password mode;
the hosted demo does not enable it.

The interface includes a pinned notice brief, live stock totals, five workflow
stages, agent-selected task cards, source comparisons, and a staged inspection helper. Fill demo inspection
inserts an explicitly authored synthetic label example. It does not submit evidence
automatically or check the hold attestation.

Browser verification on September 12, 2026 exercised login, a real Bedrock run
(COMPLETE, 8 comparisons, 5 tool calls, 4 model calls, 11.86 seconds), evidence
entry, and two 2-box confirmations ending at 4 confirmed / 0 remaining. Those
changes are isolated in `outputs/web-preview/pantry.sqlite3`; frozen fixtures and
previous recording databases are unchanged. The earlier Jif failure is still
preserved as a failed first held-out run.

See [the deployment plan and operations guide](docs/DEPLOYMENT.md) for the deployed
AWS resources, verification evidence, cost estimate, persistence, update and teardown steps.

## Run

From the project directory:

```sh
uv sync --frozen
uv run --frozen python -m unittest discover -s tests -v
uv run --frozen python -m pantry_recall.evaluate --tests
uv run --frozen python -m pantry_recall.aws_access --profile pantry-recall --region us-east-1
uv run --frozen python -m pantry_recall.agent --profile pantry-recall --region us-east-1
```

Authenticate first with AWS CLI v2:

```sh
aws login --profile pantry-recall --region us-east-1
aws sts get-caller-identity --profile pantry-recall
```

This uses browser-based temporary credentials; no credentials belong in the
repository or chat. Identity Center users configure an SSO profile instead.
`botocore[crt]` is included for the AWS browser-login credential provider.
The selected model is `amazon.nova-lite-v1:0`; `--model-id` can override it.
`aws_access` performs an actual tiny Converse request, reporting authentication,
access denial, expiry and network failure separately. It saves `outputs/aws-access.json`.

The agent saves `outputs/agent-run.json` with model-call count, usage, runtime,
tool invocations, source/version references and authoritative comparison results.
The default database is `outputs/pantry.sqlite3`; `--db` selects another file.
The baseline CLI requires all five tools and every loaded inventory row for COMPLETE status. Add
`--investigate` to enable the same seven-tool work selection used by the website. A model answer
without tool execution is reported as incomplete. There is a 12-model-call and
20-tool-call limit; requests have bounded timeouts/retries. Scope tools accept
inventory IDs, not fabricated label evidence, replacement scope or confirmations.
Briefing submission accepts task IDs and advisory reasons; the application binds
the stored task evidence so the model never needs to reproduce citation strings.
The report labels model prose as advisory/unverified and prints tool findings separately.
If the model ends without required tools or comparisons, the host requests one
bounded continuation naming only missing tools and inventory IDs. The existing
12-model-call and 20-tool-call limits cover both turns. Failed tool attempts do
not satisfy coverage. If coverage still fails, prose is retained in the audit
report and withheld from terminal presentation. A model request failure preserves
the partial tool trace and sanitized error code; it cannot publish a briefing.
If evidence or events change during inference, the report is marked
STALE_WORKFLOW_SNAPSHOT; a new run is required before presenting current findings.

## Persistent workflow replay

Run the complete synthetic evidence/confirmation sequence, then let the live
agent read its resulting state:

```sh
uv run --frozen python -m pantry_recall.workflow demo
uv run --frozen python -m pantry_recall.agent --profile pantry-recall --region us-east-1 --db outputs/workflow-demo.sqlite3 --output outputs/workflow-agent-run.json
uv run --frozen python -m pantry_recall.workflow --db outputs/workflow-demo.sqlite3 history --inventory-id missing_code
```

The offline `demo` uses a separate database, `outputs/workflow-demo.sqlite3`, and
writes `outputs/workflow-demo.json`. All confirmations are explicitly simulated.
It supplies the full code `BBD SEP 13 25 P` for four boxes on Shelf A2:

| Stage | Identification | Inspection task | Hold task | Confirmed / remaining |
| --- | --- | --- | --- | --- |
| Missing code | NEEDS_EVIDENCE | OPEN | Not created | 0 / not yet assigned |
| Code supplied | AFFECTED | DONE | OPEN | 0 / 4 boxes |
| First volunteer assertion | AFFECTED | DONE | OPEN | 2 / 2 boxes |
| Second volunteer assertion | AFFECTED | DONE | DONE | 4 / 0 boxes |

Only the hold task reaches COMPLETED_CONFIRMED. This does not record disposal,
authorize distribution, or complete other recall obligations. The hold's cited
basis is `policy.hold`; the company's conditional consumer instruction is
preserved separately. Repeating the commands reuses versions, tasks, and receipts
without resetting state or adding quantities. A repeated demo reports that it is
reusing an existing replay; use a new `--db` path for a fresh staged demonstration.

For manual terminal interaction, initialize the default database and supply the
label evidence through the human CLI:

```sh
uv run --frozen python -m pantry_recall.workflow init
uv run --frozen python -m pantry_recall.workflow show --inventory-id missing_code
uv run --frozen python -m pantry_recall.workflow evidence --inventory-id missing_code --expected-version synthetic-pantry-v2 --new-version synthetic-pantry-v3 --code "BBD SEP 13 25 P" --actor demo-volunteer --note "Synthetic inspection: all four top-panel labels checked."
```

The resulting hold task's ID for this pinned fixture is
`85fa8381-927c-5773-8bdb-ff5a05df5b55`. Explicitly record a partial synthetic
confirmation with:

```sh
uv run --frozen python -m pantry_recall.workflow confirm-hold --task-id 85fa8381-927c-5773-8bdb-ff5a05df5b55 --inventory-id missing_code --inventory-version synthetic-pantry-v3 --recall-version pearl-milling-2025-v2 --quantity 2 --unit boxes --actor demo-volunteer --confirmation-id manual-hold-1 --note "Simulation: two boxes isolated at Shelf A2." --attest-isolated
```

Use a different confirmation ID for the remaining two boxes. Reusing an ID with
the identical payload returns its original receipt; reusing it with changed
data is rejected and audited. Evidence entry and confirmation are separate CLI
commands, never model tools. The local CLI records an actor's assertion; it does
not authenticate identity or independently observe physical handling.

`fixtures/workflow/expected.json` and its lock freeze the four policy-derived
transitions before the SQLite implementation. Original notice and scope fixtures
remain unchanged. SQLite keeps raw source bytes/hashes, immutable inventory
snapshots, current cases, tasks, receipts, and append-only events. Unchanged stock
keeps its original evidence version even when another stock group creates a new
inventory snapshot. Changed stock evidence supersedes an open hold task and
requires a new confirmation; earlier receipts remain accessible.

The completed demo supports one pinned recall version per database and label/coverage
updates for existing stock groups. General stock ingestion, recall-version
migration, and reviewer acceptance of exclusion proposals are outside this demo's
implemented scope.
SQLite triggers reject history edits through normal SQL; this is local audit
history, not a tamper-proof or authenticated multiuser service.

For the dependency-free offline replay:

```sh
python -m unittest discover -s tests -v
python -m pantry_recall
python -m pantry_recall --json
```

The uv test command includes the real Strands/Bedrock adapter using stubbed AWS
responses. Plain Python skips SDK tests if those dependencies are absent.
The replay exits nonzero if a
frozen scenario fails; invalid/unavailable evidence exits with code 2. JSON output
includes raw inventory, normalized comparisons, per-condition evidence references,
source spans/hashes/timestamps, policy evidence, open task drafts, and evaluation
failures. The latest local JSON run is saved in `outputs/replay.json` (ignored
generated output).

## Pinned evidence and expected outcomes

The main demonstration remains Pearl Milling. The second fixture is Jif's May
2022 recall, limited to the 16-ounce Creamy variant. Full raw company/FDA sources
are preserved, while other Jif variants remain review items. See the separate
Jif evaluation below; its failed first live run is not relabeled as a pass.

The fixture is **F-0553-2025**, event **96134**: the
[FDA-hosted Quaker announcement](https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/quaker-issues-limited-recall-undeclared-milk-pearl-milling-company-original-pancake-waffle-mix)
for Pearl Milling Company Original Pancake & Waffle Mix. The table specifies
32 oz, printed UPC `30000 65040`, and full printed code `BBD SEP 13 25 P`.
Product, package, UPC and complete code must agree. `best_by_manufacturing_code`
stores that entire composite code, including the trailing `P`; the notice has no
separate lot-code restriction. A matching date alone is insufficient.

The company announcement is dated January 14, 2025; FDA published it January 15.
The HTML and raw enforcement JSON were acquired September 12, 2026. API metadata
reports a September 2, 2026 update. This is a pinned later snapshot for historical
replay, not a reconstruction of everything known on the recall initiation date.
The API's status and dates never determine stock applicability or action status.

The fictional **Maple Street Community Pantry, New York** has eight stock groups.
All inventory, codes outside the recalled code, evidence notes, and inspection
coverage assertions are synthetic test conditions.

| Stock group | Result |
| --- | --- |
| Affected full code | AFFECTED; hold recommended; physical-action draft open |
| Missing full code | NEEDS_EVIDENCE; inspect four boxes on Shelf A2 |
| All labels show excluded SEP 14 code | NEEDS_REVIEW; propose NOT_AFFECTED_BY_THIS_RECALL |
| Similar wording, different checked variant | Retrieved candidate; propose recall-specific exclusion |
| Mixed codes, one excluded label | NEEDS_EVIDENCE; inspect/split all nine boxes |
| Unrelated black beans | Not selected; PENDING / NOT_ASSESSED |
| Ambiguous printed-code transcription | NEEDS_REVIEW; no date/identifier repair |
| Conflicting best-by transcription | NEEDS_REVIEW; preserve both values |

`fixtures/pearl_milling_2025/` contains:

- `sources/enforcement.json`: complete original response, including metadata and
  empty `openfda` object. `sources/notice.html`: original FDA-hosted notice HTML.
- `sources/notice.txt`: deterministic text derivative. No product photo assets
  were downloaded; their original links remain in the HTML.
- `sources/acquisition.json`: exact URLs/query, retrieval times, HTTP metadata,
  record IDs, and SHA-256 hashes.
- `scope.json`: reviewed single-product scope, conditional company instruction,
  distribution context, and exact source spans. Spans use zero-based,
  end-exclusive character offsets in the UTF-8-decoded text derivative.
- `inventory.json`, `policy.json`, `expected.json`: raw synthetic inventory,
  authored pantry rules, and reference answers written before the matcher.
- `REVIEW.md`: direct source-check rationale for every scenario and attribution
  details, including the different firm names in the two source records.
- `fixture.lock.json`: V2 corrections frozen before matcher migration and first agent run.

**Expectation authorship:** V1 was source-checked and frozen before matcher
implementation; its complete fixture and lock remain in
`fixtures/archive/pearl_milling_2025_v1/`. Following the user's direct source
review, V2 corrects the field name, exclusion citations and purchase-date scenario,
with no change to the eight expected identification/action results. V2 was frozen
before the first agent run. Independent human sign-off of every synthetic
scenario remains pending; the user's notice check is recorded separately.

## Implemented boundaries

Candidate discovery reports every row and its retrieval features. Brand alone
does not retrieve a candidate, and nonselection does not imply exclusion.
Applicability uses true/false/unknown conditions; unknown identity aliases and
unverified UPC formats require review. Identifiers remain strings, including
leading zeros. UPC whitespace is normalized, but missing leading/check digits
are never inferred. Lot codes use exact comparisons and a narrow named-month
grammar; they are never fuzzy-matched or silently repaired.

An excluded code requires resolved product identity and checked labels across a
single-code stock group. One label cannot resolve a mixed bin. Geography and
receipt dates are contextual only. The matcher checks contradictory UPC/product
and date evidence before making a proposal. Unsupported or conflicting scope
requires review; altered source files, fabricated quotations, and unsupported
instruction projections are rejected. Text in a donation note has no authority.
The affected fixture deliberately has receipt on November 1, 2024, before the
notice's November 18 purchase-availability date: retail availability is not a
production/receipt applicability window. Both exclusion proposals cite the
explicit "No other Pearl Milling Company products are recalled" sentence;
the product table supplies the specific code restriction as well.

The consumer discard instruction retains its milk-allergy/sensitivity trigger,
consumer audience, and Quaker attribution. The pantry hold is explicitly
**authored application policy**. No unconditional pantry disposal instruction is
inferred. The pure matcher produces **open drafts**, with stock group, version,
quantity, unit and location. The workflow stores those as deduplicated tasks;
recalculating inventory cannot confirm a physical action.

The Pearl Milling adapter intentionally supports its one reviewed product row and code list.
The small reviewed lookalike-name mapping is an explicit synthetic annotation,
not a general product catalog. A separate Jif adapter implements its explicit
prefix-range AND plant-code restriction for one reviewed UPC. Arbitrary notices,
all-lots scope, internal item mappings, and general multi-variant expressions
remain unsupported.
Hashes detect accidental changes; they are not digital signatures or proof that
an inventory assertion is true.

## Verification

Verification uses Python 3.14.0 on Windows, Strands 1.55.1, boto3/botocore 1.43.93,
and a pinned `uv.lock`. `.gitattributes` preserves exact file bytes across
checkouts because fixture locks and evaluation protocols depend on their hashes.
**112 pantry tests pass; 18/18 frozen deterministic scenarios pass** across
two reviewed projections. The separate SemEval harnesses add 47 tests, for
**159 passing tests** with `--group evaluation`. Offline
checks use zero live model calls. Strands adapter tests separately use stubbed
Converse responses to verify real SDK tool execution, incomplete-coverage
detection, typed ID-only tool schemas, model-call bounds, and the fact that
fabricated model prose cannot complete physical actions. These are integration
tests, not evidence of live model quality. Live results belong in the agent-run report.

**Live Bedrock verification completed September 12, 2026:** the `pantry-recall`
profile in `us-east-1` successfully invoked Nova Lite. Two live Strands replays
each made **3 model calls and 4 tool calls**, compared all eight rows, and
returned tool findings matching all eight frozen expectations. The first replay
took 7.93 seconds (one observation, not a benchmark). The initial access denial
did not persist; the readiness report now records READY.
`outputs/first-live-agent-run.json` preserves the first run;
`outputs/agent-run.json` contains the final terminal demo;
`outputs/live-validation.json` compares its tool findings with the frozen answers.
The model's prose quality is not scored, and no physical action was confirmed.

| Development-fixture measure | Result |
| --- | --- |
| Distinct recalls / scenarios | 1 / 8 |
| Expected candidates retrieved | 7 / 7 |
| Candidate misses | 0 / 7 expected candidates |
| Incorrect exclusion proposals | 0 / 2 proposals |
| Incorrect affected matches | 0 / 1 affected result |
| Unexpected holds | 0 / 5 hold recommendations |
| Source-derived condition checks | 35 / 35 (five fields across seven candidates) |
| Policy checks | 63 / 63 (seven outcome fields across eight rows, plus seven coverage checks) |
| Held-out recalls | 0 |
| Initial live agent replays | 2 successful (before persistence) |
| Persistent live agent replays | 1 successful / 2 attempted; initial missing-history failure retained |
| Frozen workflow stages | 4 / 4 pass; synthetic, policy-derived expectations |

**Persistent workflow verification, September 12, 2026:** the live Strands/Bedrock
run called all five tools in four model calls (6.30 seconds, one observation).
Seven unchanged cases matched the frozen development expectations; the updated
missing-code case matched the separately frozen completed-hold outcome. The agent
created zero confirmations and preserved the two prior synthetic human receipts
and all events. `outputs/workflow-agent-run.json` contains the live trace;
`outputs/workflow-live-validation.json` records those checks.
The first attempt skipped the history tool and was correctly marked incomplete;
`outputs/workflow-agent-incomplete.json` preserves it. The workflow task prompt
was made explicit before the successful rerun. COMPLETE measures tool coverage,
not prose quality: the final model summary still omitted the confirmation details,
which the terminal's authoritative task output displays independently.

The 15 SQLite tests cover frozen transitions, preserved source bytes and versions,
reopening the database, idempotent replay, partial quantities, rejected stale or
invalid confirmations, concurrent excess-quantity protection, ambiguous/excluded
new evidence, and immutable history. Twelve SDK adapter tests cover the added
Jif tool path, bounded continuation, and failed-tool coverage, as well as
persistent-workflow checks: fabricated model confirmation has no authority,
replay preserves prior receipts, and evidence arriving during inference
invalidates the agent's current report. Rejected commands are audit events;
accepted confirmation quantities change state atomically in one transaction.

## Jif evaluation: first failure preserved

`fixtures/jif_2022/` contains a pinned enforcement record (F-1107-2022, event
90255), the archived company notice linked by FDA, the FDA investigation page,
ten synthetic stock groups, and source-checked expectations. Its lock was written
before the Jif adapter and first agent run. The [fixture review](fixtures/jif_2022/REVIEW.md)
documents the retrospective source dates, aggregated enforcement date ambiguity,
one-UPC coverage limit, per-case rationales, and pending independent human sign-off.

The lot rule checks first four digits 1274–2140 inclusive AND next three digits
425. Extra trailing digits do not turn the whole string into a numeric range.
`2000426` therefore does not match, even though it falls inside a naive seven-digit
interval. Missing lots remain unknown. One excluded label does not resolve a
mixed group. The notice also recalls 16-ounce Crunchy; our Creamy-only support
must never exclude it. These conditions come from the
[FDA lot guidance](https://www.fda.gov/food/outbreaks-foodborne-illness/outbreak-investigation-salmonella-peanut-butter-may-2022)
and its linked company announcement.

| Check | Actual result |
| --- | --- |
| Pearl Milling deterministic reference cases | 8 / 8 |
| Jif deterministic reference cases | 10 / 10 |
| Candidate misses across both fixtures | 0 / 16 expected candidates |
| Incorrect exclusion proposals | 0 / 5 proposals |
| Incorrect affected matches | 0 / 3 affected results |
| Source-derived condition checks | 80 / 80 |
| Frozen workflow stages | 4 / 4 |
| First live Jif agent run | FAILED: 0 / 10 comparisons executed; 3 model calls, 4 tools |
| Later Jif regression run | COMPLETE: 10 / 10; 3 model calls, 5 tools; 5.54 seconds |
| Blind deterministic held-out recalls / independent label sign-off | 0 / pending |

The first live run omitted `compare_scope` and its prose incorrectly described
the missing-lot stock as affected. The application rejected completion and
recorded zero actions. That is a tool-execution failure, not a measured matcher
accuracy of zero. The full first run, frozen protocol, original agent code, and
evaluation are retained in [evaluation/jif-first-run](evaluation/jif-first-run/README.md),
outside ignored generated outputs.

After inspecting that failure, a generic one-continuation coverage guard was
added and tested using stubbed SDK responses. The later live run completed all
ten comparisons without needing the continuation, so one successful rerun does
not establish a causal reliability improvement. Jif was initially held out from
agent prompt tuning, **not** deterministic adapter development; it is now a
regression fixture after feedback was inspected. The original split manifest and
failed first result are preserved. No untouched held-out recall currently remains.

Run all offline tests, both fixture evaluations, and the workflow with one command:

```sh
uv run --frozen python -m pantry_recall.evaluate --tests
```

Run another live Jif regression (separate database and output):

```sh
uv run --frozen python -m pantry_recall.agent --fixture fixtures/jif_2022 --profile pantry-recall --region us-east-1 --db outputs/jif-demo.sqlite3 --output outputs/jif-demo-agent.json
uv run --frozen python -m pantry_recall.evaluate --agent-report outputs/jif-demo-agent.json
```

Jif evidence entry uses `workflow evidence --lot-code`, while Pearl Milling uses
`--code` for the complete best-by/manufacturing code. Both preserve raw evidence
and cannot confirm physical actions.

## Recorded terminal demonstration

A **68.9-second** scripted terminal recording includes two real Bedrock runs,
the evidence update, partial/full synthetic human CLI confirmations, exclusion
review, event history, and the first Jif failure alongside its regression result.
Open `outputs/recording-demo/playback.html` and press Play. The same directory
contains `demo.cast`, `transcript.txt`, both live reports, the database, and exact
human CLI commands. This is a recorded terminal presentation; no narration or
submission-format MP4 has been produced.

To make a fresh recording, run:

```sh
uv run --frozen python -m tools.record_demo --profile pantry-recall --region us-east-1
```

The recorder creates a new directory and never resets existing work. It records
application output only. The [current browser recording script](docs/submission/VIDEO-SCRIPT.md)
provides narration and a shot list for the deployed workflow; the actual narrated
video still needs to be recorded and uploaded. [Recording notes](docs/RECORDING.md)
also document the earlier terminal capture. The cast format follows the official
[asciicast v2 specification](https://docs.asciinema.org/manual/asciicast/v2/).

Regression tests cover missing values, complete-code/date/suffix boundaries,
ambiguous dates, mixed codes, identity contradictions, leading zeros, evidence
tampering, conditional instruction attribution, injected inventory text,
deterministic replay, and acquisition error states. One test blocks socket
connections while loading and evaluating the fixture. Acquisition tests use
mocked HTTP responses. The scorecard explicitly exposes candidate misses and
false exclusions, with a regression test ensuring they are reported.

## Submission status and future validation

**Completed for this demo:** deterministic scope matching, two reviewed recall
projections, the Strands/Bedrock investigation agent, automatic follow-ups,
persistent events and human confirmation guards, the password-free public UI,
and AWS deployment. The current offline suite passes 112 tests and 18/18 scope
cases; the recorded public workflow checks passed all four stages. Submission
copy, architecture images, a Builder Center article draft, judge instructions,
portable evidence and a recording script are ready in the
[submission packet](docs/submission/START-HERE.md).

**Remaining submission steps:** record and upload the narrated demo video,
provide the AWS Builder ID, and submit the entry. The [public source repository](https://github.com/shinushibu17/pantry-recall-response-agent) is ready.
Publishing the prepared Builder Center article is optional. The earlier terminal
recording is complete, but it does not replace the current browser presentation.
Keep the deployed demo usable during judging; [operations documentation](docs/DEPLOYMENT.md)
describes its shared usage limits and maintenance.

**Future validation and broader product work:** obtain independent human sign-off
of every expected case, evaluate the revised agent on a fresh untouched recall,
and test usability with pantry volunteers. Jif's original failed first run is
preserved; subsequent Jif runs are regression checks. Broader recall support
requires additional reviewed sources and evaluations. These items are not missing
components of the demonstrated workflow, but they limit the claims it supports.

This is a historical replay with synthetic stock. The separate SemEval ST1
classification evaluation preserves its initial 0.566941 score and 41 invalid
outputs. Validation-selected regression runs on the same 997 reports scored
0.679364, then 0.735795 with title-plus-text input, then 0.765878 with Nova Pro
using the same inputs, then 0.789229 with a full training-derived taxonomy and
title/body conflict handling. All four improvements had zero invalid outputs;
that full-taxonomy run needed 145 retries for throttling. The 0.90 ST1 target remains unmet.
The subsequent nine-candidate experiment selected svm-balanced-product and scored
0.742656 on the next 997-report regression; [full results](evaluation/semeval-st1-v6/README.md)
include accuracy tradeoffs and training/split overlaps. The final evidence-first and cross-model
comparisons produced no additional test result under their frozen gain/time rules;
see the [complete experiment summary](evaluation/README.md).
These runs measure the model's category predictions,
not inventory applicability or action completion; ST2 was
not evaluated. No field accuracy claim is included. NOT_AFFECTED_BY_THIS_RECALL is limited to this
recall version and does not mean safe to distribute. No real stock was physically
handled.

## Optional acquisition

Offline tests and replay never fetch anything. To acquire a **new** candidate
snapshot for separate review:

```sh
python tools/acquire_fixture.py outputs/new-pearl-snapshot
```

The destination must not exist. This script uses an explicit January 2025 date
filter, product query, ascending initiation-date sort, and one page of at most
two records. It requires exactly the pinned record; it never silently selects
from an ambiguous/truncated result. It uses 20-second request timeouts and at
most three attempts with bounded backoff for HTTP 429/5xx. No-results, invalid
query, access denial, and unavailable states are distinct and saved in
`acquisition.json`. A failed acquisition cannot replace the working fixture.
Review new content before authoring a new scope/version/lock; reacquisition need
not produce identical HTML bytes.

API behavior was checked against the official
[query documentation](https://open.fda.gov/apis/query-parameters/),
[enforcement overview](https://open.fda.gov/apis/food/enforcement/), and
[access limits](https://open.fda.gov/apis/authentication/).

Project code is licensed under Apache 2.0 (see `LICENSE`). Source snapshots retain
their own terms and attribution, documented in the fixture's `REVIEW.md`.
The agent uses the Strands Agents SDK and AWS SDK (Apache 2.0); dependency versions
and transitive packages are recorded in `uv.lock`. Amazon Nova is invoked through
Bedrock under AWS's service terms. Source evidence keeps its separate attribution.

Integration follows the official [Strands Bedrock provider documentation](https://strandsagents.com/docs/user-guide/concepts/model-providers/amazon-bedrock/)
and [custom tool documentation](https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/).
Local authentication follows [AWS browser login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).
