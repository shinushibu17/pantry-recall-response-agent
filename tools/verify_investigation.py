"""Exercise actual agent-selected next steps and automatic follow-ups over HTTP.

Run with python -m tools.verify_investigation. Every model response is preserved
before assertions; an incomplete run is a failure, never a successful demo.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from uuid import uuid4

from tools.verify_deployment import Visitor


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url",required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    visitor=Visitor(args.url)
    state=visitor.request("/api/state")
    summary={"url":args.url,"synthetic":True,"runs":[],"status":"RUNNING"}

    def wait_run(scene,previous=None,identifier=None):
        deadline=time.monotonic()+180
        run=None
        while time.monotonic()<deadline:
            status=visitor.request("/api/agent-status")
            key=identifier or status["latest_run_id"]
            if key and key!=previous:
                run=visitor.request("/api/agent/"+key)
                if run["status"]!="RUNNING":break
            time.sleep(2)
        (args.output/(scene+".json")).write_text(json.dumps(run or {"status":"TIMED_OUT"},indent=2),encoding="utf-8")
        assert run and run["status"]=="COMPLETE" and run["current"], f"{scene}: agent did not complete a current briefing"
        report=run["report"];brief=report["briefing"]
        assert len(report["validated_results"])==8 and brief and brief["priorities"]
        assert all(p.get("evidence_binding")=="stored_task" and p["cited_evidence_ids"]==p["task"]["evidence_refs"] for p in brief["priorities"]), "Briefing must retain the selected tasks' exact stored evidence"
        if previous:assert run["trigger"]["kind"]=="workflow_change"
        record={"scene":scene,"trigger":run["trigger"]["kind"],"status":run["status"],"model_calls":report["model_calls"],
                "tools":len(report["tool_calls"]),"runtime_seconds":report["runtime_seconds"],
                "history_inspected":brief["history_inspected"],"selected_stock":[p["task"]["inventory_id"] for p in brief["priorities"]],
                "evidence_binding":"stored_task"}
        summary["runs"].append(record)
        print(json.dumps(record),flush=True)
        return run

    try:
        identifier="investigate-"+str(uuid4())
        visitor.request("/api/agent",{"request_id":identifier})
        initial=wait_run("initial",identifier=identifier)
        case=visitor.request("/api/evidence",{"inventory_id":"missing_code","expected_version":state["inventory"]["version"],
            "new_version":"checked-"+str(uuid4()),"actor":"Synthetic verification",
            "changes":{"best_by_manufacturing_code":"BBD SEP 13 25 P","evidence_note":"Authored synthetic all-unit inspection, not real stock."}})
        evidence=wait_run("after-evidence",previous=initial["id"])
        hold=next(t for t in case["tasks"] if t["type"]=="PERFORM_ACTION" and t["status"]=="OPEN")
        selected=next(p["task"] for p in evidence["report"]["briefing"]["priorities"] if p["task"]["inventory_id"]=="missing_code")
        assert selected["remaining_quantity"]==4
        command={"confirmation_id":str(uuid4()),"task_id":hold["task_id"],"inventory_id":"missing_code",
                 "inventory_version":case["inventory_version"],"recall_version":case["recall_version"],"quantity":2,"unit":"boxes",
                 "actor":"Synthetic verification","note":"Explicit simulated two-box hold.","attest_isolated":True}
        partial_receipt=visitor.request("/api/confirm-hold",command)
        partial=wait_run("partial-hold",previous=evidence["id"])
        selected=next(p["task"] for p in partial["report"]["briefing"]["priorities"] if p["task"]["inventory_id"]=="missing_code")
        assert selected["remaining_quantity"]==2 and partial_receipt["remaining_quantity"]==2
        assert visitor.request("/api/confirm-hold",command)==partial_receipt
        assert visitor.request("/api/agent-status")["latest_run_id"]==partial["id"]
        command["confirmation_id"]=str(uuid4())
        visitor.request("/api/confirm-hold",command)
        completed=wait_run("completed-hold",previous=partial["id"])
        brief=completed["report"]["briefing"]
        assert "missing_code" in brief["history_inspected"]
        assert all(p["task"]["task_id"]!=hold["task_id"] for p in brief["priorities"])
        final=visitor.request("/api/state")
        assert final["confirmation_count"]==2
        summary.update(status="PASS",checked_at=datetime.now(timezone.utc).isoformat(),human_receipts=2,agent_confirmations=0)
    except Exception as error:
        summary.update(status="FAIL",failure=str(error))
        raise
    finally:
        try:
            visitor.request("/api/follow-up",{"enabled":False})
        except Exception:
            summary["pause_followups"]="Could not confirm pause; inspect server status"
        (args.output/"verification.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")


if __name__=="__main__":main()
