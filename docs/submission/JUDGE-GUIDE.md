# Try Pantry Recall Response Agent

**[Open the public AWS demo](https://d1vhm9p26zmdc7.cloudfront.net). No password required.**
Every visitor receives a separate fictional pantry. All stock and volunteer
actions in the walkthrough are synthetic.

## A four-minute walkthrough

1. Click **Start recall agent**. Wait for COMPLETE and eight comparisons. Open
   its tool details and next-check cards to see case histories and recommendations.
2. Select **Label inspection**, use **Fill demo inspection**, and save the
   authored example. The four missing-code boxes become AFFECTED. A follow-up
   briefing starts automatically, labeled **Triggered by your update**.
3. Use the separate human hold form to record a simulated two-box confirmation
   with the required reviewer, note and attestation. Two boxes remain open.
   Another agent run follows the receipt.
4. Confirm the other two boxes in the same way. The hold task is complete; after
   the next briefing, the agent suggests other open work. This does not confirm
   disposal or authorize distribution.
5. Inspect **Different printed code** or **Similar product wording**. Show the
   exclusion proposal, its source spans and the pending review state. Open case
   history to see evidence versions and the two separate human receipts.

Recommendations can vary. The walkthrough's evidence, quantities and state
transitions are deterministic; the model's task order is advisory. Pause
follow-ups when finished.

The shared live allowance is 20 starts per UTC day, with one concurrent run.
If inference is unavailable, the interface reports that state; accepted evidence
and receipts remain saved. The [portable verification records](EVIDENCE.md)
document completed runs without presenting a replay as a fresh model call.

Evaluation shaped the behavior to inspect here: a first Jif run skipped scope
comparisons, prompting a bounded continuation for missing tool work; a later
citation failure prompted task selection with exact evidence attached by the
application. The same failed browser session recovered, and the subsequent
four-stage public check completed. [EVIDENCE.md](EVIDENCE.md) links the preserved
failures and follow-up records. These are specific regression checks, not a
general reliability measurement.

SemEval informed the deployed Nova Pro model and richer case context: raw stock
fields, exact notice excerpts and explicit task definitions. Separate pantry
workflow checks govern deployment. The benchmark's best completed test ST1 is
**0.7892**; **0.8073** is validation-only. Neither measures this walkthrough's accuracy.

## Reproduce locally

From the downloaded [public repository](https://github.com/shinushibu17/pantry-recall-response-agent)
root, with Python 3.11+ and uv installed:

```sh
uv sync --frozen
uv run --frozen python -m pantry_recall.evaluate --tests
uv run --frozen python -m pantry_recall.web
```

Open http://127.0.0.1:8080. The evaluation uses pinned local fixtures and makes
no model calls. Initial dependency installation needs internet access.

For live inference, use your own AWS credentials with permission to invoke
`amazon.nova-pro-v1:0` in `us-east-1`. In PowerShell, set your configured profile
and region before starting the server:

```powershell
$env:AWS_PROFILE = "pantry-recall"
$env:AWS_REGION = "us-east-1"
uv run --frozen python -m pantry_recall.aws_access --profile pantry-recall --region us-east-1
uv run --frozen python -m pantry_recall.web
```

Replace `pantry-recall` with your own profile name. The access diagnostic makes
a real model invocation; local live inference uses your AWS account. The hosted
demo uses its EC2 instance role and needs no visitor AWS credentials.

## Where to inspect the implementation

| Responsibility | Source |
| --- | --- |
| Agent, tool wrappers and execution bounds | [agent.py](../../pantry_recall/agent.py) |
| Persistent evidence and human receipts | [store.py](../../pantry_recall/store.py) |
| Deterministic scope comparison | [matching.py](../../pantry_recall/matching.py) |
| Web application entry point | [web.py](../../pantry_recall/web.py) |
| Main notice and frozen expectations | [Pearl review](../../fixtures/pearl_milling_2025/REVIEW.md) |
| First live Jif failure | [Evaluation record](../../evaluation/jif-first-run/README.md) |
| Agent boundaries and deployment | [Agent role](../AGENT-ROLE.md), [deployment](../DEPLOYMENT.md) |

The two recall projections are deliberately narrow. The Jif adapter supports
the reviewed 16-ounce creamy product projection, not every product in the full
notice. Expected outcomes are authored and source-reviewed; independent human
sign-off of all cases is pending.
