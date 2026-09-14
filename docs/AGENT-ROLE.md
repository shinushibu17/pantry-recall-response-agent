# Agent design

One Strands agent uses Amazon Nova Pro on Bedrock to investigate pantry cases
and recommend the next work. Reviewed scope comparisons and stored workflow
state determine product identification and action quantities.

## Tools and decisions

| Tool | Purpose |
| --- | --- |
| `load_recall_fixture` | Read the pinned notice, scope and source evidence |
| `load_inventory` | Read the current stock groups |
| `find_candidates` | Identify plausible recall matches |
| `compare_scope` | Evaluate identifiers with true, false and unknown outcomes |
| `get_work_queue` | Read open tasks, their type definitions and submission requirements |
| `get_case_history` | Retrieve raw stock, exact case-linked evidence, conditions and prior receipts |
| `submit_briefing` | Propose up to three existing task IDs with advisory reasons |

The host requires complete comparison coverage, histories for changed stock,
current task bindings and a next step for changed stock when one is available.
It attaches selected tasks' exact stored evidence. The model does not supply
label observations, confirm holds, release food or alter pinned sources.
Its reasons remain advisory; evidence binding does not validate every sentence.

## Execution and follow-ups

Runs are bounded to 16 model calls and 20 tool calls. Missing tool coverage can
trigger one continuation naming only missing tools and stock IDs. Failed tools
do not satisfy coverage; incomplete and stale briefings are withheld.

Nova Pro uses temperature 0, topK 1 and at most 3,072 output tokens, following
[AWS tool-use guidance](https://docs.aws.amazon.com/nova/latest/userguide/tools-troubleshooting.html).
The application filters deliberation tags from advisory output. A model-output
failure is reported separately from missing credentials or permissions.
`BEDROCK_MODEL_ID` selects the web model and is recorded in every live report.
The default is `amazon.nova-pro-v1:0`; Nova Lite remains available for rollback.

After the first manual start, accepted evidence and hold receipts trigger
follow-ups. Pending updates coalesce while a run is active. Event cursors,
reports and control state persist in SQLite. Replayed or rejected writes do not
trigger inference. Pause stops new automatic starts; restarting the demo keeps
the old audit and creates a separate replay.

The hosted app permits one concurrent agent and 20 starts per UTC day across
visitors. Inference failures leave accepted evidence and receipts intact.
No background recall feed is monitored.

## Verification

[Recorded evidence](submission/EVIDENCE.md) shows four completed public stages
and recovery of a previously failed citation run. The first Jif failure is
preserved separately. Forced SDK tests cover the continuation path; the later
live Jif pass did not need it. These are specific regression checks, not a
measured general reliability rate.

A fresh live workflow check uses four agent starts and pauses follow-ups:

```sh
uv run --frozen python -m tools.verify_investigation --url http://127.0.0.1:8080 --output outputs/new-workflow-check
```
