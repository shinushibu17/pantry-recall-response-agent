# Terminal recording and narration

Open `outputs/recording-demo/playback.html` in a browser and press **Play**.
The 68.9-second recording is real application output from two Bedrock runs and
scripted, explicitly synthetic volunteer actions. It is not a desktop capture,
not a report of real stock handling, and not yet a narrated MP4.

| Scene | Suggested narration |
| --- | --- |
| Missing evidence | “A pantry has four boxes on Shelf A2 but is missing the full label code. That becomes a specific inspection task.” |
| Live agent | “Strands calls deterministic tools through Amazon Bedrock. The recall evidence is pinned, and unknown information stays unknown.” |
| Evidence arrives | “In this simulation, a volunteer checks every box. The complete code matches. Inspection is done; the hold task is still open.” |
| Agent rereads state | “The agent sees the new evidence but cannot manufacture a confirmation that stock was physically isolated.” |
| Two confirmations | “The first assertion covers two boxes, leaving two open. The second finishes only this isolation task—not disposal or distribution clearance.” |
| Audit history | “An excluded code remains a reviewer proposal. Earlier evidence, tasks, and human assertions remain in the event history.” |
| Evaluation | “Eighteen authored scope cases pass across two reviewed projections. The first live Jif test exposed a skipped tool and was kept as a failure. The later regression passes; this is not field accuracy or a fresh held-out pass.” |

For a new capture:

```powershell
uv run --frozen python -m pantry_recall.evaluate --tests
uv run --frozen python -m tools.record_demo --profile pantry-recall --region us-east-1
```

The recorder refuses an existing output directory and saves:

- `playback.html`: offline player with recorded timings, no CDN or external assets.
- `demo.cast` and `transcript.txt`: terminal event stream and readable transcript.
- `agent-initial.json` and `agent-after-evidence.json`: actual live SDK traces.
- `human-cli-commands.json`: exact simulated evidence and confirmation commands.
- `pantry.sqlite3` and `recording.json`: resulting workflow state and recording metadata.

Before submission, add narration and export/capture the playback to the required
video format, verify current hackathon deliverables, and obtain permission before
publishing the repository or submitting externally. The public UI and AWS
deployment are now live; see the browser walkthrough below. A fresh untouched recall is required for a new held-out score
after the Jif feedback was used; keep the original failed result visible.


## Public browser walkthrough

Open [the live AWS demo](https://d1vhm9p26zmdc7.cloudfront.net); no login or local server is needed.

1. Click **Start recall agent** and wait for COMPLETE and all eight comparisons.
   Show the three suggested next checks, selected case histories and tool arguments.
2. Select **Label inspection**, then **Fill demo inspection**. Explain that this
   is an authored synthetic label example, then save the evidence.
3. Wait for the automatic briefing labeled **Triggered by your update**; no
   manual recheck is needed. Show the missing-code change and AFFECTED with the
   physical hold still unconfirmed. Record an explicitly simulated two-box hold
   with the required attestation. The next automatic briefing uses two remaining boxes.
4. Confirm the other two boxes. Wait for the agent to inspect the receipt and
   suggest other open work; the completed hold cannot be selected. Show the history and the separate source notice
   instructions versus the pantry's precautionary hold policy.
5. Show **Different printed code** and **Similar product wording** as pending
   review proposals. Restart demo creates a fresh replay and keeps the old audit.

Each visitor has separate demo state. Live runs share a 20-starts-per-UTC-day
allowance. Record the actual result; never relabel an incomplete run as success.
This walkthrough uses four live starts; pause follow-ups afterward. Advisory
priority ordering is not a food-safety risk ranking. The earlier terminal
recording remains a baseline and has not been replaced by a new narrated capture.
This guide does not replace the remaining narrated video/export work.
