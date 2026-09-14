"""Persistent historical replay and explicit human evidence/confirmation CLI."""

import argparse
import json
from pathlib import Path

from .confirmations import HoldConfirmation, record_human_confirmation
from .fixtures import DEFAULT_FIXTURE, digest, read_json
from .store import Store, WorkflowError


EXPECTATIONS = DEFAULT_FIXTURE.parent / "workflow"


def load_expectations() -> dict:
    lock = read_json(EXPECTATIONS / "fixture.lock.json")
    for name, expected in lock["files"].items():
        if digest((EXPECTATIONS / name).read_bytes()) != expected:
            raise WorkflowError("EXPECTATIONS_CHANGED", "Frozen workflow expectations changed")
    return read_json(EXPECTATIONS / "expected.json")


def stage_summary(case: dict, stage: str) -> dict:
    identify = next((t for t in case["tasks"] if t["type"] == "IDENTIFY_STOCK"), None)
    hold = next((t for t in case["tasks"] if t["type"] == "PERFORM_ACTION" and t["inventory_version"] == case["inventory_version"]), None)
    return {"stage": stage, "identification_state": case["identification_state"], "action_state": case["action_state"],
            "identify_status": identify["status"] if identify else None, "hold_status": hold["status"] if hold else None,
            "confirmed_quantity": hold["confirmed_quantity"] if hold else 0,
            "remaining_quantity": hold["remaining_quantity"] if hold else None}


def run_demo(store: Store) -> dict:
    """Explicit simulation: no physical action is performed or independently verified."""
    expected = load_expectations()
    overview = store.initialize()
    fresh = overview["inventory_version"] == expected["initial_inventory_version"] and overview["confirmation_count"] == 0
    stages = [stage_summary(store.case("missing_code"), "initial")]
    case = store.supply_evidence("missing_code", expected["initial_inventory_version"], expected["updated_inventory_version"],
                                 {"best_by_manufacturing_code": expected["new_code"],
                                  "evidence_note": "Synthetic volunteer checked all four top-panel labels: BBD SEP 13 25 P."}, "demo-volunteer")
    stages.append(stage_summary(case, "evidence_arrived"))
    hold = next(t for t in case["tasks"] if t["type"] == "PERFORM_ACTION" and t["inventory_version"] == expected["updated_inventory_version"])
    receipts = []
    for number, stage in [(1, "partial_confirmation"), (2, "full_confirmation")]:
        receipts.append(record_human_confirmation(store, HoldConfirmation(
            confirmation_id=f"workflow-demo-hold-{number}", task_id=hold["task_id"], inventory_id="missing_code",
            inventory_version=expected["updated_inventory_version"], recall_version=expected["recall_version"],
            quantity=2, unit="boxes", actor="demo-volunteer", attest_isolated=True,
            note=f"SIMULATION: volunteer reports isolating two boxes at Shelf A2, batch {number}.")))
        stages.append(stage_summary(store.case("missing_code"), stage))
    checks = [{"stage": actual["stage"], "passed": actual == reference, "expected": reference, "actual": actual}
              for actual, reference in zip(stages, expected["stages"])] if fresh else []
    return {"status": "PASS" if (all(check["passed"] for check in checks) if fresh else stages[-1] == expected["stages"][-1]) else "FAIL",
            "synthetic": True, "fresh_replay": fresh, "database": str(store.path),
            "note": "Human confirmations are simulated; no real products were handled. Existing replay receipts are reused without advancing state again.",
            "checks": checks, "receipts": receipts, "history": store.history("missing_code"),
            "unrelated_case": store.case("unrelated"), "exclusion_proposal": store.case("excluded_code"),
            "event_count": store.overview()["event_count"]}


def print_case(case: dict) -> None:
    print(f"{case['inventory_id']}: {case['identification_state']} / {case['action_state']}")
    print(f"  Recall {case['recall_version']}; stock evidence {case['inventory_version']}")
    for task in case["tasks"]:
        print(f"  {task['type']} {task['status']}: {task['quantity']} {task['unit']} at {task['location']}")
        print(f"    ID {task['task_id']}; version {task['inventory_version']}")
        if task["type"] == "PERFORM_ACTION":
            print(f"    Hold only: confirmed {task['confirmed_quantity']}; remaining {task['remaining_quantity']}")
        print(f"    Basis: {task['basis']}; evidence: {', '.join(task['evidence_refs'])}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, help="Defaults to outputs/pantry.sqlite3, or outputs/workflow-demo.sqlite3 for demo")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init")
    for command in ("show", "history"):
        child = commands.add_parser(command)
        child.add_argument("--inventory-id", default="missing_code")
    evidence = commands.add_parser("evidence")
    for field in ("inventory-id", "expected-version", "new-version", "actor", "note"):
        evidence.add_argument("--" + field, required=True)
    identifiers = evidence.add_mutually_exclusive_group(required=True)
    identifiers.add_argument("--code", help="Full best-by/manufacturing code, such as the Pearl Milling top-panel code")
    identifiers.add_argument("--lot-code", help="Separate printed lot identifier, such as the Jif lot code")
    confirm = commands.add_parser("confirm-hold")
    for field in ("confirmation-id", "task-id", "inventory-id", "inventory-version", "recall-version", "unit", "actor", "note"):
        confirm.add_argument("--" + field, required=True)
    confirm.add_argument("--quantity", type=int, required=True)
    confirm.add_argument("--attest-isolated", action="store_true", help="Explicit synthetic volunteer assertion; never supplied by the agent")
    demo = commands.add_parser("demo", help="Simulate evidence arrival and two human confirmations")
    demo.add_argument("--output", type=Path, default=Path("outputs/workflow-demo.json"))
    args = parser.parse_args(argv)
    store = Store(args.db or Path("outputs/workflow-demo.sqlite3" if args.command == "demo" else "outputs/pantry.sqlite3"))
    try:
        if args.command == "init":
            result = store.initialize()
            print(f"Initialized {store.path}; {len(result['cases'])} cases; {result['event_count']} events. Existing state is preserved.")
        elif args.command == "show":
            print_case(store.case(args.inventory_id))
        elif args.command == "history":
            print(json.dumps(store.history(args.inventory_id), indent=2))
        elif args.command == "evidence":
            field = "lot_code" if args.lot_code is not None else "best_by_manufacturing_code"
            print_case(store.supply_evidence(args.inventory_id, args.expected_version, args.new_version,
                                            {field: args.lot_code if args.lot_code is not None else args.code, "evidence_note": args.note}, args.actor))
        elif args.command == "confirm-hold":
            result = record_human_confirmation(store, HoldConfirmation(**{field: getattr(args, field) for field in HoldConfirmation.__dataclass_fields__}))
            print(json.dumps(result, indent=2))
        else:
            result = run_demo(store)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
            print("SYNTHETIC REPLAY: no real products were handled.")
            for check in result["checks"]:
                stage = check["actual"]
                print(f"{stage['stage']}: {stage['identification_state']} / {stage['action_state']}; inspection={stage['identify_status']}; hold={stage['hold_status']}; confirmed={stage['confirmed_quantity']}; remaining={stage['remaining_quantity']}")
            if not result["fresh_replay"]:
                print("Existing replay: reused recorded evidence and confirmations; no state reset.")
            print(f"Workflow: {result['status']}; {len(result['checks'])} new stage checks; report: {args.output}")
            print_case(result["history"]["case"])
            return 0 if result["status"] == "PASS" else 2
        return 0
    except WorkflowError as error:
        print(f"Rejected ({error.code}): {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
