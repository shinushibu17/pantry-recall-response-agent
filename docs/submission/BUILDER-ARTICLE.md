# #AgentsForHumans: Building a Pantry Recall Agent That Keeps Human Confirmation Separate

A pantry volunteer needs more than a summary of a recall notice. They need to
know which stock needs checking, which label detail is missing, and which action
is still outstanding after someone finds the answer.

For Agents for Humans, I built Pantry Recall Response Agent: a historical recall
replay for a fictional community pantry, with a Strands agent on Amazon Bedrock.
The [public demo](https://d1vhm9p26zmdc7.cloudfront.net) requires no password and
gives each visitor a separate synthetic pantry.

## Start with four boxes and one missing code

The main demonstration uses a pinned January 2025
[FDA-hosted Pearl Milling Company notice](https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts/quaker-issues-limited-recall-undeclared-milk-pearl-milling-company-original-pancake-waffle-mix).
Four synthetic boxes are missing the complete printed best-by/manufacturing
code. That is an unresolved identification question. It should create an
inspection task, not silently become a mismatch.

When the volunteer supplies the matching code, the inspection is finished. The
physical hold is still open. Confirming two boxes leaves two outstanding;
confirming the remaining two closes that particular hold task. The agent then
returns to other open work.

This separation drives the design: evidence about the product and a human's
assertion about an action are different records.

## Make the notice inspectable before adding an agent

I saved the source notice and enforcement record with retrieval metadata and
content hashes, then froze synthetic examples and expected outcomes before the
corresponding matching logic. Source projections preserve the original evidence.

The main notice has a full printed code, not a separate lot-code restriction.
The matcher also needs to distinguish Original from similarly worded variants.
A date describing when consumers could first purchase the product must not
become a production window. Those details belong in reviewed comparisons, where
unknown values remain unknown.

The application separately labels the notice's consumer instructions and its
own precautionary pantry hold policy. It does not attribute the authored hold
workflow to the issuer.

## Give the agent a useful decision to make

The Strands agent uses Amazon Nova Lite through Bedrock. Seven tools expose the
pinned recall, current inventory, candidate retrieval, scope comparisons, open
work, case histories and briefing submission.

The agent chooses additional histories to investigate and selects up to three
open tasks with advisory reasons. After the first start, accepted evidence and
hold receipts trigger another investigation. It can follow a case from missing
information to a partially completed hold and then move on when that task closes.

The agent factory makes those boundaries visible in code:

```python
return Agent(
    model=model,
    tools=build_tools(fixture, trace, store, investigation),
    system_prompt=SYSTEM_PROMPT,
    callback_handler=None,
    hooks=[trace],
    retry_strategy=None,
    tool_executor=SequentialToolExecutor(),
    load_tools_from_directory=False,
)
```

This excerpt uses [Strands' agent and tool interfaces](https://strandsagents.com/docs/user-guide/quickstart/python/).
`build_tools` supplies the permitted operations; the host records the trace and
owns the bounded coverage continuation.

The host checks coverage and current task state before displaying the briefing.
The model has no tool that writes a human confirmation, releases stock, or
disposes of it. Its rationale is advisory; evidence binding does not prove every
sentence of generated reasoning.

## Two failures that made the agent better

The first live Jif check called tools but never called the scope comparator.
The result was INCOMPLETE_TOOL_COVERAGE: zero of ten comparisons executed.
I preserved the failure and added a bounded continuation that names the missing
work without supplying expected answers. Later Jif checks are regression tests,
because the original result has already influenced development. The later live
Jif pass did not need the continuation; forced SDK tests cover that recovery
path.

Another live run completed the comparisons but repeatedly invented citation
suffixes. The validator rejected them until the run hit its limit. Asking the
model to retry the same citation syntax was not solving the underlying problem.

I changed the briefing tool so the agent selects existing task IDs and supplies
reasons. The application attaches the exact evidence references already stored
on those tasks. The original evidence validator remains in place, and regression
tests cover the failed selections and rejection of unknown tasks. The previously
failing browser session subsequently completed without resetting the pantry.

Evaluation therefore changed two concrete agent behaviors: how it recovers
missing tool work and how its selected tasks receive source citations. The later
four-stage public walkthrough completed successfully with those changes in
place. That is evidence of recovery from observed failures; it does not establish
a general reliability rate or measured volunteer time savings.

## Deploy a demonstration people can try

CloudFront serves the public HTTPS entry point and connects through a VPC origin
to the Python application on EC2. A retained encrypted EBS volume holds SQLite
events, evidence versions, human receipts and agent reports. S3 stores private
release artifacts; the EC2 instance role supplies Bedrock permissions. Systems
Manager supports maintenance without an SSH entry point.

I kept the runtime small enough to inspect. One agent, a persistent workflow and
an explicit human-write boundary were sufficient for this milestone.

## What the evidence supports

The current offline suite passes 112 tests and 18 frozen synthetic scenarios
across two reviewed recall projections. The latest four-stage public check
completed every briefing, recorded two simulated human hold receipts and zero
agent confirmations. Separate deployment checks verified visitor isolation,
idempotent receipts and persistence across a service restart.

I also tested a separate classification problem using the released
[SemEval 2025 food-hazard dataset](https://food-hazard-detection-semeval-2025.github.io/).
The best completed ST1 score at the submission freeze is **0.7892**, compared with the original
**0.5669** baseline, on all 997 test reports. This composite is not an accuracy
percentage or a measure of the deployed Strands workflow. The best configuration
uses Nova Pro, title and report text, four retrieved training examples, and the
complete training-derived category taxonomy.

That benchmark also supplied a useful failure: a supervised hybrid's tiny
validation gain disappeared on the test regression, which fell to **0.7427**.
I kept that result and every earlier run. The desired 0.90 ST1 score has not been
reached. Repeated test exposure, training/split text overlaps, and possible
foundation-model contamination limit what these comparisons can establish.
The evidence package preserves the protocols, predictions, raw responses and
unchanged labels. ST2 was not evaluated.

A final combination of Nova Pro hazard predictions and DeepSeek product
predictions reached **0.8073 on validation**. It completed after the frozen
test-launch cutoff, so it has no test result and does not replace the completed
0.7892 test score.

The combined local suite now passes **159 tests**, including the separate
benchmark harnesses. These experiments informed model and classification
comparisons; they did not change the deployed Nova Lite agent. The coverage and
citation fixes came from evaluating the actual agent workflow.

These are prototype checks, not measured pantry outcomes. Independent sign-off
of every expected case, a new untouched recall evaluation and a volunteer pilot
remain next steps. There is no live recall feed, OCR or measured time-saving claim.

The most useful lesson was deciding what the agent should be trusted to choose.
It can investigate and explain the next work while the application preserves
exact evidence, quantities and the human record of completion.

Try the [live historical replay](https://d1vhm9p26zmdc7.cloudfront.net), starting
with the four boxes whose code is missing. All inventory and actions are
synthetic, and live inference has a shared daily demo allowance. The
[source repository](https://github.com/shinushibu17/pantry-recall-response-agent)
includes the Strands implementation, pinned fixtures, tests, architecture and
preserved evaluation records.
