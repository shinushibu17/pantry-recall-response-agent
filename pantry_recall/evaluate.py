"""One offline command for both recall fixtures and the frozen workflow replay."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .__main__ import score
from .fixtures import DEFAULT_FIXTURE, load_fixture, read_json
from .matching import evaluate_inventory
from .store import Store
from .workflow import run_demo


def evaluate_suite(agent_report: Path | None = None) -> dict:
    root = DEFAULT_FIXTURE.parent
    manifest = read_json(root / "evaluation-manifest.json")
    evaluations = []
    for entry in manifest["fixtures"]:
        path = root / entry["path"]
        fixture, expected = load_fixture(path), read_json(path / "expected.json")
        findings = evaluate_inventory(fixture)
        result = score(findings, expected)
        result.update(fixture=entry["path"], family=entry["family"],
                      expectation_freeze=fixture["lock"]["frozen_at"],
                      source_derived_conditions=sum(len(expected["conventions"]["source_derived"]) for c in expected["cases"] if c["candidate"]),
                      expected_exclusion_proposals=sum(c["proposed_identification_state"] is not None for c in expected["cases"]),
                      expected_affected=sum(c["identification_state"] == "AFFECTED" for c in expected["cases"]))
        evaluations.append(result)
    with TemporaryDirectory() as temp:
        workflow = run_demo(Store(Path(temp) / "workflow.sqlite3"))
    live = None
    if agent_report:
        report = read_json(agent_report)
        versions = {row["recall_version"] for row in report.get("validated_results", [])}
        selected = next((entry for entry in manifest["fixtures"] if load_fixture(root / entry["path"])["scope"]["evidence"] == report.get("source_evidence")), None)
        if selected is None or len(versions) > 1:
            raise ValueError("Agent report does not contain one complete supported recall version")
        fixture_path = root / selected["path"]
        fixture = load_fixture(fixture_path)
        live = score(report["validated_results"], read_json(fixture_path / "expected.json"))
        live.update(agent_status=report["status"], model_calls=report["model_calls"],
                    tool_calls=len(report["tool_calls"]), runtime_seconds=report["runtime_seconds"],
                    physical_actions_confirmed=report["physical_actions_confirmed"], report=str(agent_report),
                    source_evidence_matches=report["source_evidence"] == fixture["scope"]["evidence"],
                    policy_evidence_matches=report["policy_evidence"] == fixture["policy"]["evidence"],
                    model_prose_scored=False)
        live["unexecuted_case_count"] = len(report.get("uncompared_inventory_ids", []))
        live["candidate_retrieval_misses"] = None if not report["validated_results"] else live["candidate_retrieval_misses"]
        live["coverage_note"] = "Unexecuted comparisons count as evaluation failures, not measured matching errors or retrieval misses. Model prose is not a scope verdict."
    success = all(not result["failures"] for result in evaluations) and workflow["status"] == "PASS"
    if live:
        success &= (not live["failures"] and live["agent_status"] == "COMPLETE" and live["source_evidence_matches"]
                    and live["policy_evidence_matches"] and live["physical_actions_confirmed"] == 0)
    return {"status": "PASS" if success else "FAIL", "recall_families": len(evaluations),
            "scenarios": sum(result["scenarios"] for result in evaluations),
            "evaluations": evaluations, "workflow": {"status": workflow["status"], "stage_checks": workflow["checks"]},
            "live_agent": live, "limits": manifest["limits"], "independent_human_signoff": "pending"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent-report", type=Path, help="Optional existing live trace; this command never invokes a model")
    parser.add_argument("--output", type=Path, default=Path("outputs/evaluation.json"))
    parser.add_argument("--tests", action="store_true", help="Also run the full offline unit/SDK test suite")
    args = parser.parse_args()
    result = evaluate_suite(args.agent_report)
    if args.tests:
        import unittest
        suite = unittest.defaultTestLoader.discover(str(DEFAULT_FIXTURE.parent.parent / "tests"))
        tests = unittest.TextTestRunner(verbosity=1).run(suite)
        result["unit_tests"] = {"run": tests.testsRun, "failures": len(tests.failures), "errors": len(tests.errors), "skipped": len(tests.skipped)}
        if not tests.wasSuccessful():
            result["status"] = "FAIL"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    for row in result["evaluations"]:
        print(f"{row['fixture']} ({row['split']}): {row['passed']}/{row['scenarios']}; candidate misses={row['candidate_retrieval_misses']}; incorrect exclusion proposals={row['incorrect_exclusion_proposals']}; incorrect affected={row['incorrect_affected_matches']}")
        for failure in row["failures"]:
            print(json.dumps(failure))
    print(f"Workflow: {result['workflow']['status']}; {len(result['workflow']['stage_checks'])} frozen stage checks")
    if result["live_agent"]:
        live = result["live_agent"]
        print(f"Live trace: {live['agent_status']}; {live['passed']}/{live['scenarios']}; model calls={live['model_calls']}; tool calls={live['tool_calls']}; no model prose score")
    print(result["limits"])
    print(f"Evaluation: {result['status']}; report: {args.output}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
