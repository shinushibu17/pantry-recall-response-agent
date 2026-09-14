"""Exercise the deployed public HTTP API with isolated synthetic visitors."""

import argparse
from http.cookiejar import CookieJar
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import build_opener, HTTPCookieProcessor, Request
from uuid import uuid4


class Visitor:
    def __init__(self, url):
        self.url = url.rstrip("/")
        self.client = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, path, body=None, origin=None):
        request = Request(self.url+path, data=None if body is None else json.dumps(body).encode(),
                          headers={"Content-Type":"application/json", "X-Pantry-Request":"reviewer", "Origin":origin or self.url})
        with self.client.open(request, timeout=30) as response:
            return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url")
    parser.add_argument("--no-agent", action="store_true")
    parser.add_argument("--restart-service", action="store_true", help="Also restart the owned AWS service through SSM and verify the same visitor's receipts")
    parser.add_argument("--profile", default="pantry-recall")
    parser.add_argument("--output", type=Path, default=Path("outputs/deployment/verification-latest"), help="New directory; existing evidence is never overwritten")
    args = parser.parse_args()
    deployment_output = Path("outputs/deployment")
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    url = args.url or json.loads((deployment_output/"live.json").read_text())["Url"]
    alice, bob = Visitor(url), Visitor(url)
    report = {"url":url,"checks":[],"synthetic":True}
    def check(condition, name):
        if not condition: raise AssertionError(name)
        report["checks"].append(name)
        print("PASS",name,flush=True)
    check(alice.request("/health")["status"]=="ok","HTTPS health")
    initial = alice.request("/api/state")
    check(initial["demo_mode"] and len(initial["cases"])==8,"Password-free eight-stock workspace")
    bob.request("/api/state")
    if not args.no_agent:
        run_id = str(uuid4())
        alice.request("/api/agent",{"request_id":run_id})
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            run=alice.request("/api/agent/"+run_id)
            if run["status"]!="RUNNING": break
            time.sleep(2)
        check(run["status"]=="COMPLETE" and run["current"],"Live Bedrock agent COMPLETE from AWS runtime")
        check(len(run["report"]["validated_results"])==8,"All eight comparisons executed")
        report["agent"]={key:run["report"].get(key) for key in ("status","model_id","provider","model_calls","tool_calls","runtime_seconds","usage")}
        (output/"public-agent-run.json").write_text(json.dumps(run["report"],indent=2),encoding="utf-8")
        # This verifier isolates the HTTP/confirmation boundary. The four-stage
        # investigate verifier separately exercises automatic model follow-ups.
        alice.request("/api/follow-up", {"enabled":False})
    version="remote-check-"+str(uuid4())
    case=alice.request("/api/evidence",{"inventory_id":"missing_code","expected_version":initial["inventory"]["version"],"new_version":version,
        "changes":{"best_by_manufacturing_code":"BBD SEP 13 25 P","evidence_note":"Scripted remote HTTP verification: all four synthetic top-panel labels checked."},"actor":"Deployment verifier"})
    check(case["identification_state"]=="AFFECTED","Missing code becomes affected with supplied evidence")
    check(bob.request("/api/history?id=missing_code")["case"]["identification_state"]=="NEEDS_EVIDENCE","Other visitor remains untouched")
    task=next(t for t in case["tasks"] if t["type"]=="PERFORM_ACTION" and t["status"]=="OPEN")
    command={"confirmation_id":str(uuid4()),"inventory_id":"missing_code","inventory_version":case["inventory_version"],"recall_version":case["recall_version"],
        "task_id":task["task_id"],"quantity":2,"unit":"boxes","actor":"Deployment verifier","note":"Synthetic two-box isolation check.","attest_isolated":True}
    partial=alice.request("/api/confirm-hold",command)
    check(partial["remaining_quantity"]==2 and partial["task_status"]=="OPEN","Partial hold leaves two boxes open")
    check(alice.request("/api/confirm-hold",command)==partial,"Exact replay does not double-count")
    command["confirmation_id"]=str(uuid4())
    final=alice.request("/api/confirm-hold",command)
    check(final["remaining_quantity"]==0 and final["action_state"]=="COMPLETED_CONFIRMED","Final hold closes only its specified quantity")
    try:
        alice.request("/api/session",{},origin="https://unrelated.example")
    except HTTPError as error:
        check(error.code==403,"Cross-origin writes rejected")
    else: raise AssertionError("Cross-origin write unexpectedly accepted")
    if args.restart_service:
        import boto3
        live=json.loads((deployment_output/"live.json").read_text())
        check(url==live["Url"],"Restart target matches the owned deployment")
        before=alice.request("/api/history?id=missing_code")
        ssm=boto3.Session(profile_name=args.profile,region_name="us-east-1").client("ssm")
        commands=["set -eu", "mountpoint -q /var/lib/pantry", "findmnt -n -o SOURCE,TARGET,FSTYPE --target /var/lib/pantry",
                  "systemctl restart pantry-recall", "systemctl is-active pantry-recall",
                  "for attempt in $(seq 1 30); do if curl -fsS http://127.0.0.1:8080/health; then exit 0; fi; sleep 1; done; exit 1"]
        command_id=ssm.send_command(InstanceIds=[live["InstanceId"]],DocumentName="AWS-RunShellScript",
                                    Parameters={"commands":commands})["Command"]["CommandId"]
        deadline=time.monotonic()+90
        invocation={"Status":"TimedOut"}
        while time.monotonic()<deadline:
            time.sleep(2)
            try:
                invocation=ssm.get_command_invocation(CommandId=command_id,InstanceId=live["InstanceId"])
            except ssm.exceptions.InvocationDoesNotExist:
                continue
            if invocation["Status"] not in ("Pending","InProgress","Delayed"):
                break
        check(invocation["Status"]=="Success","Service restarted with a mounted persistent data disk")
        check(alice.request("/api/history?id=missing_code")==before,"Same visitor's complete history survives service restart")
        check(alice.request("/api/confirm-hold",command)==final,"Confirmation replay stays idempotent after service restart")
        check(bob.request("/api/history?id=missing_code")["case"]["identification_state"]=="NEEDS_EVIDENCE",
              "Visitor isolation survives service restart")
        report["persistence"]={"command_id":command_id,"status":invocation["Status"],"mount_and_health":invocation["StandardOutputContent"]}
    report.update(status="PASS",checked_at=time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()))
    (output/"verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("Remote verification passed.",flush=True)


if __name__=="__main__": main()
