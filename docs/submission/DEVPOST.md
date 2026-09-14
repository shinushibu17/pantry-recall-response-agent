# Devpost copy

Use the sections that match the submission form. Keep pending URLs and account
details in the entry's dedicated fields, not in the project story.

## Project name

Pantry Recall Response Agent

## Tagline

Turn a recall notice into a specific pantry check—and follow it through with source evidence and human confirmation.

## Short description

A Strands agent on Amazon Bedrock helps a fictional community pantry investigate
a historical recall. It selects next checks, follows new label evidence, and
revisits outstanding work after human confirmations. Deterministic tools preserve
unknown information, while an auditable workflow keeps identifying recalled
stock separate from confirming that someone physically isolated it.

## Inspiration

A recall notice identifies a product. A volunteer still needs to find the right
boxes, read their labels, and document what happened next. Mixed donations and
incomplete tracking make that last step difficult, as described in
[Food Safety Magazine's account of the recall last mile](https://www.food-safety.com/articles/8136-recalls-and-the-true-last-mile).

I built around one practical question: **Which shelf needs a person next, and
what evidence or action is still missing?**

## What it does

The password-free demo opens a separate synthetic pantry for each visitor.
A real Strands agent, running on Amazon Bedrock, compares eight stock groups
against a pinned Pearl Milling recall, investigates case histories, and proposes
up to three next checks with advisory reasons and stored source evidence.

Four boxes on Shelf A2 lack their full printed code. They remain unresolved
until a volunteer supplies the evidence. In the demonstration, that code matches:
the inspection finishes, but a precautionary hold remains open. A simulated
two-box confirmation leaves two outstanding. Confirming the remaining two closes
that hold task, and the agent returns to other open work automatically.

The interface preserves the notice, exact quoted spans, inventory versions,
tasks, and human assertions. An exclusion proposal still needs review; it never
becomes automatic permission to distribute food.

## How I built it

I started with source bytes, reviewed scope projections, synthetic inventory,
and expected outcomes frozen before the corresponding matcher implementation.
The scope engine treats a missing identifier as unknown, not a mismatch.

One Strands agent uses Amazon Nova Lite on Bedrock and seven typed tools:
`load_recall_fixture`, `load_inventory`, `find_candidates`, `compare_scope`,
`get_work_queue`, `get_case_history`, and `submit_briefing`. It decides which
additional histories to inspect and which open tasks to recommend. The host
checks complete comparison coverage, current task state and changed-case
coverage, then attaches the selected tasks' exact stored evidence references.

Accepted label updates and human hold receipts trigger follow-up investigations
after the first start. SQLite persists events, evidence snapshots, receipts,
agent reports and pending follow-ups. Human-write endpoints are separate from
the model's toolset.

The Python application runs on EC2 behind CloudFront HTTPS with a VPC origin.
An encrypted EBS data volume holds visitor state; a private S3 bucket stores
release artifacts. An instance role supplies Bedrock access, and Systems Manager
supports deployment maintenance.

## Challenges I ran into

The first live Jif evaluation skipped the scope-comparison tool entirely:
**INCOMPLETE_TOOL_COVERAGE, 0/10 comparisons executed**. I preserved that failed
result and added a bounded coverage continuation. The later live Jif pass did
not need that continuation; forced SDK tests exercise the recovery path. The
later pass is a regression result, not a new held-out score.

A later browser run compared every item but repeatedly invented citation
suffixes and exhausted its call limit. The fix was to let the agent select
existing task IDs and supply reasons, while the host binds exact stored evidence.
The same previously failing browser session then completed without resetting
the pantry. This also made the trust boundary easier to explain.

## Accomplishments I'm proud of

- A deployed, password-free agent that reacts to evidence and confirmation
  events, with visible tools and case history.
- 112 passing automated tests and 18/18 frozen synthetic scope cases across
  two reviewed recall projections.
- Four complete public Bedrock workflow stages in the latest recorded check,
  with two simulated human hold receipts and zero agent confirmations.
- Explicit separation of issuer instructions, precautionary pantry policy,
  uncertain identification, and recorded human action.

I also evaluated category classification on all 997 released SemEval 2025 Task 9
test reports. The original Nova Lite ST1 composite was **0.5669**, with 41 invalid
outputs preserved. The best completed regression reached **0.7892** with Nova
Pro, full training-derived taxonomy guidance and retrieved training examples.
Later experiments did not establish the requested **0.90 ST1** target. I kept
the negative results as part of the evidence. A later combination reached
**0.8073 on validation**, but finished after the frozen test-launch cutoff and
has no test result. It does not replace the completed 0.7892 test score.

These experiments informed model and classification comparisons; they did not
change the deployed Nova Lite agent. ST1 is a separate classification composite,
not accuracy or an evaluation of that agent workflow. These are comparisons after test exposure;
training/split exact-body overlaps and possible model contamination limit the
claims. ST2 was not evaluated. All **159 local tests pass**, including the
separate benchmark harnesses. The [evaluation summary](../../evaluation/README.md)
links frozen protocols, predictions, raw responses and verification records.

## What I learned

Evaluation directly shaped the agent's reliability. Skipped comparisons led to
a bounded continuation for missing tool work; invented citation identifiers led
to task selection with exact evidence attached by the application. Subsequent
regression checks and the four-stage public walkthrough completed successfully.
The original failures remain preserved. These observations demonstrate recovery
from specific failures, without establishing a general success rate or measured
improvement in volunteer productivity.

The model's useful discretion is in investigating and explaining the next work.
Exact identifiers, current quantities and completion receipts need enforceable
application checks. Preserving a failed run is also useful: it shows precisely
which reliability claim the next change must earn.

## What's next

An independent review of the fixture expectations, a new untouched recall
evaluation, and a volunteer usability study would test the assumptions this
prototype cannot settle. A broader product would also need additional reviewed
scope adapters, recall ingestion and operational monitoring.

This is a historical replay with synthetic inventory, not a live alert service
or a field-validated safety system. No pantry pilot or time-saving measurement
has been completed. Model priorities are advisory, and recorded confirmations
are human assertions rather than sensor-verified physical actions.

## Built with

Strands Agents SDK, Amazon Bedrock, Amazon Nova Lite, Amazon EC2, Amazon
CloudFront, Amazon EBS, Amazon S3, AWS IAM, AWS Systems Manager, AWS
CloudFormation, Python, SQLite, JavaScript, HTML, CSS, uv.

## Links / track

- Live demo: https://d1vhm9p26zmdc7.cloudfront.net
- Suggested track: Good Neighbor
- Source repository: https://github.com/shinushibu17/pantry-recall-response-agent
- Video and AWS Builder ID: supply your actual published video link and account
  identifier in the form; see [the completion checklist](START-HERE.md).
