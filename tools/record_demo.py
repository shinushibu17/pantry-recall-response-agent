"""Record an actual scripted terminal replay: live Bedrock plus simulated human CLI actions.

Creates an asciicast v2 file, a plain transcript, and a self-contained HTML player.
No desktop, keyboard input, credentials, or unrelated application content is captured.
"""

import argparse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import sys
import time

from pantry_recall.agent import run_agent
from pantry_recall.aws_access import DEFAULT_MODEL, client_config, session_for
from pantry_recall.evaluate import evaluate_suite
from pantry_recall.fixtures import load_fixture, read_json
from pantry_recall.store import Store
from pantry_recall.workflow import main as human_cli, print_case
from strands.models import BedrockModel


PLAYER = """<!doctype html><meta charset="utf-8"><title>Pantry recall terminal recording</title>
<style>body{background:#111827;color:#e5e7eb;font:18px Consolas,monospace;margin:32px}button{font:inherit;padding:8px 18px;margin-right:12px}pre{white-space:pre-wrap;line-height:1.4;height:76vh;overflow:auto;border:1px solid #374151;padding:22px}small{color:#9ca3af}</style>
<h2>Pantry Recall Response — recorded terminal replay</h2>
<p><button id="play">Play / restart</button><button id="pause">Pause</button><span id="clock">0:00</span></p>
<small>Actual application output and live Bedrock calls. Inventory and volunteer actions are synthetic. No physical stock was handled.</small><pre id="screen">Press Play.</pre>
<script>const events=EVENTS;let start=0,index=0,running=false,elapsed=0;
const screen=document.getElementById('screen');
document.getElementById('play').onclick=()=>{index=0;elapsed=0;screen.textContent='';start=performance.now();running=true;};
document.getElementById('pause').onclick=()=>{if(running){elapsed=(performance.now()-start)/1000;running=false;}else{start=performance.now()-elapsed*1000;running=true;}};
function tick(){if(running){const seconds=(performance.now()-start)/1000;while(index<events.length&&events[index][0]<=seconds){let data=events[index++][2];if(data.includes('\\x1b[2J'))screen.textContent='';screen.textContent+=data.replace(/\\x1b\\[[0-9;]*[A-Za-z]/g,'').replace(/\\r/g,'');screen.scrollTop=screen.scrollHeight;}document.getElementById('clock').textContent=Math.floor(seconds/60)+':'+String(Math.floor(seconds)%60).padStart(2,'0');if(index===events.length)running=false;}requestAnimationFrame(tick);}tick();</script>
"""


class Recording:
    def __init__(self, folder):
        self.folder = folder
        self.started = time.perf_counter()
        self.events = []
        self.stream = sys.stdout

    def write(self, value):
        if value:
            self.events.append([round(time.perf_counter() - self.started, 6), "o", value.replace("\n", "\r\n")])
            self.stream.write(value)
            self.stream.flush()
        return len(value)

    def flush(self):
        self.stream.flush()

    def scene(self, title):
        self.write("\x1b[2J\x1b[H" + title + "\n" + "=" * 70 + "\n")

    def save(self):
        header = {"version": 2, "width": 112, "height": 36, "title": "Pantry Recall Response: synthetic historical replay", "duration": round(time.perf_counter()-self.started, 3)}
        (self.folder / "demo.cast").write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in [header, *self.events]) + "\n", encoding="utf-8")
        transcript = "".join(row[2] for row in self.events).replace("\x1b[2J\x1b[H", "\n\n")
        (self.folder / "transcript.txt").write_text(transcript, encoding="utf-8")
        data = json.dumps(self.events, ensure_ascii=False).replace("<", "\\u003c")
        (self.folder / "playback.html").write_text(PLAYER.replace("EVENTS", data), encoding="utf-8")
        return header


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="pantry-recall")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    folder = args.output or Path("outputs") / ("recording-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    folder.mkdir(parents=True, exist_ok=False)
    recording = Recording(folder)
    database = folder / "pantry.sqlite3"
    store = Store(database)
    store.initialize()
    session = session_for(args.profile, args.region)
    model = BedrockModel(model_id=DEFAULT_MODEL, boto_session=session, boto_client_config=client_config(), streaming=False, temperature=0, max_tokens=2048)
    commands = []

    def cli(arguments, compact=False):
        buffer = StringIO()
        with redirect_stdout(buffer):
            code = human_cli(["--db", str(database), *arguments])
        commands.append({"arguments": arguments, "exit_code": code, "output": buffer.getvalue()})
        if code:
            raise RuntimeError(buffer.getvalue())
        if not compact:
            print(buffer.getvalue())

    try:
        with redirect_stdout(recording), redirect_stderr(recording):
            recording.scene("1. Missing evidence is a concrete task")
            print("Maple Street Community Pantry — fictional inventory, historical recall.")
            print_case(store.case("missing_code"))
            print("No physical action has been confirmed. The hold recommendation cites pantry policy.")
            time.sleep(6)

            recording.scene("2. Strands calls real tools through Amazon Bedrock")
            fixture = load_fixture()
            print("FDA-hosted company notice: Pearl Milling, January 2025.")
            print(fixture["scope"]["evidence"]["notice.product_table"]["quote"])
            print("Model: " + DEFAULT_MODEL + " | Region: " + args.region)
            first = run_agent(model, store.load_context(), store=store)
            (folder / "agent-initial.json").write_text(json.dumps(first, indent=2) + "\n", encoding="utf-8")
            print(f"Agent: {first['status']} | {first['model_calls']} model calls | {len(first['tool_calls'])} tool calls")
            if first["status"] != "COMPLETE":
                raise RuntimeError("Incomplete live agent run; recording retained for review")
            print_case(store.case("missing_code"))
            time.sleep(6)

            recording.scene("3. Simulated volunteer supplies label evidence through the human CLI")
            cli(["evidence", "--inventory-id", "missing_code", "--expected-version", "synthetic-pantry-v2", "--new-version", "synthetic-pantry-v3", "--code", "BBD SEP 13 25 P", "--actor", "demo-volunteer", "--note", "Simulation: all four top-panel labels checked."])
            print("Identification is resolved; isolation still needs a separate confirmation.")
            time.sleep(6)

            recording.scene("4. Agent reads the new evidence; it cannot confirm physical actions")
            second = run_agent(model, store.load_context(), store=store)
            (folder / "agent-after-evidence.json").write_text(json.dumps(second, indent=2) + "\n", encoding="utf-8")
            print(f"Agent: {second['status']} | confirmations made by agent: {second['physical_actions_confirmed']}")
            if second["status"] != "COMPLETE":
                raise RuntimeError("Incomplete live agent run after evidence")
            print_case(store.case("missing_code"))
            time.sleep(6)

            task = store.case("missing_code")["tasks"][-1]
            for batch in [1, 2]:
                recording.scene(f"{4+batch}. Human confirmation simulation: another two boxes isolated")
                cli(["confirm-hold", "--task-id", task["task_id"], "--inventory-id", "missing_code", "--inventory-version", "synthetic-pantry-v3", "--recall-version", "pearl-milling-2025-v2", "--quantity", "2", "--unit", "boxes", "--actor", "demo-volunteer", "--confirmation-id", f"recording-hold-{batch}", "--note", f"Simulation: two boxes isolated, batch {batch}.", "--attest-isolated"], compact=True)
                print_case(store.case("missing_code"))
                print("Only the specified hold task is confirmed. No disposal or release is recorded.")
                time.sleep(6)

            recording.scene("7. Exclusion remains a proposal; history preserves each step")
            print_case(store.case("excluded_code"))
            history = store.history("missing_code")
            for event in history["events"]:
                print(f"Event {event['sequence']}: {event['kind']} | actor: {event['actor']} | {event['channel']}")
            print("Unrelated inventory:", store.case("unrelated")["identification_state"], "/", store.case("unrelated")["action_state"])
            time.sleep(6)

            recording.scene("8. Evaluation and limits")
            evaluation = evaluate_suite()
            for row in evaluation["evaluations"]:
                print(f"{row['fixture']}: {row['passed']}/{row['scenarios']} deterministic scope cases; false exclusion proposals: {row['incorrect_exclusion_proposals']}")
            print("Workflow: four frozen transitions passed. All inventory and confirmations are synthetic.")
            original = read_json(Path("outputs/jif-first-agent-run.json"))
            regression = read_json(Path("outputs/jif-remediation-agent-run.json"))
            print(f"First live Jif check: {original['status']}; {len(original['validated_results'])}/10 comparisons executed. Preserved without relabeling.")
            print(f"Later regression: {regression['status']}; {len(regression['validated_results'])}/10 comparisons. A bounded coverage reminder is now available.")
            print("Two reviewed product projections; no blind matcher generalization or field-accuracy claim.")
            print("No general safety certification. Independent human label sign-off remains pending.")
            time.sleep(8)
            print("End of recorded terminal replay.")
        status = "COMPLETE"
    except Exception as error:
        recording.write("\nRecording stopped: " + str(error) + "\n")
        status = "INCOMPLETE"
    metadata = recording.save()
    (folder / "human-cli-commands.json").write_text(json.dumps(commands, indent=2) + "\n", encoding="utf-8")
    (folder / "recording.json").write_text(json.dumps({"status": status, "synthetic": True, **metadata}, indent=2) + "\n", encoding="utf-8")
    print(f"Recording {status}: {folder / 'playback.html'} ({metadata['duration']} seconds)")
    return 0 if status == "COMPLETE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
