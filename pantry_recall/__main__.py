"""Print an offline replay and an explicit development-fixture scorecard."""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

from .fixtures import DEFAULT_FIXTURE, FixtureError, load_fixture, read_json
from .matching import evaluate_inventory


def score(results: list[dict], expected: dict) -> dict:
    by_id = {result["inventory_id"]: result for result in results}
    failures = []
    counts = {"candidate_retrieval_misses": 0, "incorrect_exclusion_proposals": 0,
              "incorrect_affected_matches": 0, "unexpected_holds": 0}
    for case in expected["cases"]:
        actual = by_id.get(case["inventory_id"])
        if actual is None:
            failures.append({"inventory_id": case["inventory_id"], "field": "missing_result"})
            counts["candidate_retrieval_misses"] += int(case["candidate"])
            continue
        projection = {key: actual[key] for key in (
            "identification_state", "proposed_identification_state", "missing_fields", "review_fields", "action_state")}
        projection.update({"candidate": actual["candidate"]["included"],
                           "conditions": {k: v["truth"] for k, v in actual["conditions"].items()},
                           "task_type": actual["task"]["type"] if actual["task"] else None})
        for key, value in projection.items():
            if value != case[key]:
                failures.append({"inventory_id": case["inventory_id"], "field": key, "expected": case[key], "actual": value})
        counts["candidate_retrieval_misses"] += int(case["candidate"] and not projection["candidate"])
        counts["incorrect_exclusion_proposals"] += int(projection["proposed_identification_state"] == "NOT_AFFECTED_BY_THIS_RECALL" and case["proposed_identification_state"] != projection["proposed_identification_state"])
        counts["incorrect_affected_matches"] += int(projection["identification_state"] == "AFFECTED" and case["identification_state"] != "AFFECTED")
        counts["unexpected_holds"] += int(projection["action_state"] == "HOLD_RECOMMENDED" and case["action_state"] != "HOLD_RECOMMENDED")
    expected_ids = {case["inventory_id"] for case in expected["cases"]}
    for inventory_id in set(by_id) - expected_ids:
        failures.append({"inventory_id": inventory_id, "field": "unexpected_result"})
    failed_ids = {failure["inventory_id"] for failure in failures}
    return {"split": expected.get("split", "development"), "distinct_recalls": 1, "scenarios": len(expected_ids),
            "passed": len(expected_ids - failed_ids),
            "expected_candidates": sum(case["candidate"] for case in expected["cases"]),
            "retrieved_candidates": sum(result["candidate"]["included"] for result in results),
            **counts, "failures": failures,
            "agent_held_out_recalls": int(expected.get("split") == "agent-held-out"), "held_out_recalls": 0, "model_calls": 0,
            "human_label_signoff": "pending", "physical_action_transitions": "not scored by this scope-only comparison"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Include all condition, source and inventory evidence")
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()
    start = perf_counter()
    try:
        fixture = load_fixture(args.fixture)
        results = evaluate_inventory(fixture)
        report = score(results, read_json(args.fixture / "expected.json"))
    except (FixtureError, OSError, ValueError, KeyError) as error:
        print(f"Fixture unavailable or invalid: {error}", file=sys.stderr)
        return 2
    report["runtime_seconds"] = round(perf_counter() - start, 6)
    if args.json:
        print(json.dumps({"evaluation": report, "sources": fixture["acquisition"],
                          "source_evidence": fixture["scope"]["evidence"],
                          "policy_evidence": fixture["policy"]["evidence"], "results": results}, indent=2, ensure_ascii=False))
    else:
        print(f"Historical recall {fixture['scope']['recall_number']}; synthetic pantry; offline replay")
        print(f"Notice date: {fixture['acquisition']['source_timestamps']['fda_publish_date']}; snapshot: {fixture['acquisition']['notice']['retrieved_at']}")
        print(f"API last_updated: {fixture['acquisition']['source_timestamps']['api_last_updated']}; API snapshot: {fixture['acquisition']['enforcement']['retrieved_at']}")
        for result in results:
            outcome = result["identification_state"]
            if result["proposed_identification_state"]:
                outcome += f" -> proposed {result['proposed_identification_state']}"
            selected = "candidate" if result["candidate"]["included"] else "not selected"
            print(f"{result['inventory_id']}: {selected}; {outcome}; {result['action_state']}")
        print(json.dumps(report, indent=2))
        print("All tasks are open drafts. Recall-specific exclusion does not mean safe to distribute.")
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
