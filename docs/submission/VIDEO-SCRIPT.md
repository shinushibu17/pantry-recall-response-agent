# Recording script — target 4:20, hard limit 5:00

Record the actual deployed browser workflow, with your narration. This is a
script and shot list, not a finished presentation or a substitute for a live
result. Keep the app large enough to read at 1080p. Use only synthetic entries;
close unrelated tabs and account consoles before recording.

## Before recording

- Open https://d1vhm9p26zmdc7.cloudfront.net in a fresh demo replay. Verify the
  agent is idle and at least four shared starts remain for this sequence.
- Keep [architecture.svg](architecture.svg) and [EVIDENCE.md](EVIDENCE.md) in
  nearby tabs. Practice the human form without submitting duplicate actions.
- Use a reviewer name such as `Demo volunteer` and a note such as
  `Synthetic demonstration: two boxes isolated`. The attestation is part of the
  simulation; do not imply real food was handled.
- The model may choose different task priorities. Narrate the results actually
  shown. If a run fails, record that status or transparently record a later
  attempt; never present cached output as a fresh success.

## Screen sequence and spoken script

### 0:00–0:30 · The problem

**Show:** Pantry dashboard, source notice and Shelf A2's missing-code case.

> A recall notice tells you which product is involved. A pantry volunteer still
> needs to find the right boxes and document what happens next. This is Pantry
> Recall Response Agent, built for the Good Neighbor track. It turns a notice
> into specific inventory checks and follows the work as new evidence arrives.
> This pantry, its stock and every action I'm showing are synthetic.

### 0:30–1:05 · Start the real agent

**Do:** Click **Start recall agent**. During the wait, show notice evidence. When
complete, show eight comparisons, tool details and suggested checks.

> This is a real Strands agent using Amazon Nova Lite on Bedrock. It reads the
> recall, compares the inventory, investigates case histories and proposes the
> next checks. The deterministic tools preserve uncertainty. These four boxes
> are missing the full printed code, so they need an inspection. The agent's
> recommendations are advisory; it cannot declare that a person handled stock.

### 1:05–1:50 · Evidence changes the work

**Do:** Select **Label inspection**, **Fill demo inspection**, then save. Show
the full `BBD SEP 13 25 P` code, AFFECTED state and automatic follow-up.

> I'll supply the demo inspection, representing a volunteer checking every box.
> The complete code matches, including the trailing P. Identification changes
> to affected, and the inspection task finishes. But physical isolation is still
> outstanding. Saving the evidence triggers the agent automatically. It reads
> the changed case and updates its recommendations from the current work queue.

### 1:50–2:40 · A human confirms a quantity

**Do:** Submit a simulated two-box hold with reviewer, note and attestation. Wait
for follow-up; show two remaining. Confirm the other two and show the next run.

> This separate form records a human assertion. I confirm two boxes, leaving two
> open. The agent follows that receipt; it cannot manufacture the other two.
> Now I confirm the remaining boxes. That hold task closes, and the next briefing
> returns to other open work. The history keeps both receipts. Closing a hold
> does not confirm disposal or authorize distribution.

### 2:40–3:15 · Show the evidence boundary

**Show:** Excluded-code or similar-product review proposal, expanded source
evidence, and distinction between source instructions and pantry policy.

> A different printed code and a similarly named product need careful treatment
> too. Here the proposed exclusion cites the stored notice evidence and still
> awaits review. The precautionary hold is our pantry policy; the notice has its
> own instructions addressed to consumers. Exact references come from stored
> tasks, while the model supplies its advisory reasons.

### 3:15–3:45 · AWS architecture

**Show:** Architecture image full screen; point to Strands/Bedrock, deterministic
tools, separate human-write route and persistent events.

> CloudFront connects to a Python service on EC2. Strands calls Bedrock through
> the instance role. SQLite on encrypted EBS preserves evidence, events and
> receipts. New workflow events trigger follow-ups after the first start. The
> model's tools are separate from the endpoints that record human actions.

### 3:45–4:20 · Evidence and close

**Show:** Evidence summary, then return to the finished case and remaining work.

> The prototype passes 112 tests and 18 frozen synthetic scope cases. The latest
> public check completed all four workflow stages with two human receipts and
> zero agent confirmations. Evaluation changed the agent: skipped comparisons
> led to bounded recovery, and invented citations led to application-bound
> evidence. The original failures remain preserved; later passes are regression
> checks. Next are independent expectation review and a volunteer pilot. Make
> the next check clear, retain its evidence, and keep human confirmation separate.

## Export and upload

The spoken script is intentionally short enough to leave room for clicks and
model waits. Rehearse once and trim narration before exceeding five minutes.
If editing removes waits, mark the cut or note that waits were shortened; preserve
the order and actual results. Upload the finished video publicly to YouTube or
Vimeo, verify it while signed out, and paste its URL into the submission.
The earlier terminal `playback.html` is a useful backup demonstration, but it
does not show the complete current browser workflow. Pause follow-ups afterward.
