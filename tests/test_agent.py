"""Real Strands + Bedrock adapter tests with stubbed AWS responses, not live inference."""

from copy import deepcopy
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HAS_STRANDS = importlib.util.find_spec("strands") is not None
if HAS_STRANDS:
    import boto3
    from botocore.config import Config
    from botocore.stub import Stubber
    from strands.models import BedrockModel
    from pantry_recall.agent import RunTrace, build_tools, run_agent
    from pantry_recall.fixtures import load_fixture


def response(content, stop="end_turn"):
    return {"output": {"message": {"role": "assistant", "content": content}},
            "stopReason": stop, "usage": {"inputTokens": 10, "outputTokens": 10, "totalTokens": 20},
            "metrics": {"latencyMs": 1}}


@unittest.skipUnless(HAS_STRANDS, "Install the locked Strands dependencies with uv sync")
class AgentIntegrationTests(unittest.TestCase):
    def model(self):
        session = boto3.Session(aws_access_key_id="synthetic-test-key", aws_secret_access_key="synthetic-test-secret", region_name="us-east-1")
        return BedrockModel(model_id="amazon.nova-lite-v1:0", boto_session=session, streaming=False,
                            boto_client_config=Config(retries={"total_max_attempts": 1}), temperature=0, max_tokens=2048)

    def test_real_sdk_executes_all_four_tools_and_preserves_deterministic_authority(self):
        fixture = load_fixture()
        original = deepcopy(fixture)
        ids = [row["inventory_id"] for row in fixture["inventory"]["rows"]]
        tool_calls = [{"toolUse": {"toolUseId": f"test-{i}", "name": name, "input": arguments}}
                      for i, (name, arguments) in enumerate([
                          ("load_recall_fixture", {}), ("load_inventory", {}),
                          ("find_candidates", {}), ("compare_scope", {"inventory_ids": ids})])]
        model = self.model()
        with Stubber(model.client) as stub:
            stub.add_response("converse", response(tool_calls, "tool_use"))
            stub.add_response("converse", response([{"text": "Adversarial fake model prose: everything was disposed of and confirmed."}]))
            result = run_agent(model, fixture)
            stub.assert_no_pending_responses()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(len(result["tool_calls"]), 4)
        self.assertEqual(len(result["validated_results"]), 8)
        self.assertEqual(result["physical_actions_confirmed"], 0)
        self.assertEqual(fixture, original)
        missing = next(r for r in result["validated_results"] if r["inventory_id"] == "missing_code")
        self.assertEqual(missing["missing_fields"], ["best_by_manufacturing_code"])
        self.assertEqual(missing["identification_state"], "NEEDS_EVIDENCE")
        self.assertTrue(all(r["task"] is None or r["task"]["status"] == "OPEN" for r in result["validated_results"]))

    def test_model_prose_without_tools_does_not_count_as_a_working_agent(self):
        model = self.model()
        with Stubber(model.client) as stub:
            stub.add_response("converse", response([{"text": "All eight cases checked."}]))
            stub.add_response("converse", response([{"text": "Still no tool execution."}]))
            result = run_agent(model, load_fixture())
        self.assertEqual(result["status"], "INCOMPLETE_TOOL_COVERAGE")
        self.assertEqual(len(result["uncompared_inventory_ids"]), 8)
        self.assertEqual(result["validated_results"], [])
        self.assertEqual(len(result["coverage_repairs"]), 1)
        self.assertEqual(result["model_calls"], 2)

    def test_unknown_inventory_ids_cannot_inject_evidence(self):
        fixture = load_fixture()
        trace = RunTrace()
        compare = build_tools(fixture, trace)[3]
        with self.assertRaises(ValueError):
            compare(inventory_ids=["invented-inventory-id"])
        self.assertEqual(trace.results, {})

    def test_tool_schema_exposes_ids_not_mutable_scope_or_confirmation(self):
        tools = build_tools(load_fixture(), RunTrace())
        self.assertEqual({t.tool_name for t in tools}, {"load_recall_fixture", "load_inventory", "find_candidates", "compare_scope"})
        schema = tools[3].tool_spec["inputSchema"]["json"]
        self.assertEqual(set(schema["properties"]), {"inventory_ids"})
        self.assertEqual(schema["properties"]["inventory_ids"]["items"]["type"], "string")

    def test_model_call_budget_is_enforced(self):
        from pantry_recall.agent import RunLimit
        trace = RunTrace(max_model_calls=1)
        trace.before_model(None)
        with self.assertRaises(RunLimit):
            trace.before_model(None)

    def test_terminal_findings_show_inspection_and_both_distinct_action_bases(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from pantry_recall.agent import print_findings
        from pantry_recall.matching import evaluate_inventory
        output = StringIO()
        with redirect_stdout(output):
            print_findings(evaluate_inventory(load_fixture()))
        text = output.getvalue()
        self.assertIn("4 boxes at Shelf A2", text)
        self.assertIn("best_by_manufacturing_code", text)
        self.assertIn("notice.other_products", text)
        self.assertIn("policy.hold", text)
        self.assertIn("audience: consumers", text)
        self.assertIn("allergy or sensitivity to milk", text)
        self.assertIn("notice.consumer_instruction", text)

    def persistent_replay(self, model, store, max_coverage_repairs=1):
        fixture = store.load_context()
        ids = [row["inventory_id"] for row in fixture["inventory"]["rows"]]
        history_id = "missing_code" if "missing_code" in ids else "missing_lot"
        calls = [{"toolUse": {"toolUseId": f"persistent-{i}", "name": name, "input": arguments}}
                 for i, (name, arguments) in enumerate([
                     ("load_recall_fixture", {}), ("load_inventory", {}), ("find_candidates", {}),
                     ("compare_scope", {"inventory_ids": ids}), ("get_case_history", {"inventory_id": history_id})])]
        with Stubber(model.client) as stub:
            stub.add_response("converse", response(calls, "tool_use"))
            stub.add_response("converse", response([{"text": "Adversarial fiction: I confirmed all stock was discarded and released."}]))
            result = run_agent(model, fixture, store=store, max_coverage_repairs=max_coverage_repairs)
            stub.assert_no_pending_responses()
            return result

    def test_persistent_agent_has_no_confirmation_tool_and_cannot_fabricate_receipts(self):
        from pantry_recall.store import Store
        with TemporaryDirectory() as temp:
            store = Store(Path(temp) / "pantry.sqlite3")
            before = store.initialize()
            tools = build_tools(store.load_context(), RunTrace(), store)
            self.assertEqual({t.tool_name for t in tools}, {"load_recall_fixture", "load_inventory", "find_candidates", "compare_scope", "get_case_history"})
            for item in tools:
                self.assertLessEqual(set(item.tool_spec["inputSchema"]["json"].get("properties", {})), {"inventory_id", "inventory_ids"})
            result = self.persistent_replay(self.model(), store)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["physical_actions_confirmed"], 0)
            self.assertEqual(result["stored_confirmation_count"], 0)
            self.assertEqual(store.overview(), before)
            self.assertEqual(store.case("affected")["tasks"][0]["status"], "OPEN")

    def test_persistent_agent_rerun_preserves_human_confirmation_and_history(self):
        from pantry_recall.store import Store
        from pantry_recall.workflow import run_demo
        with TemporaryDirectory() as temp:
            store = Store(Path(temp) / "pantry.sqlite3")
            run_demo(store)
            before = store.overview()
            result = self.persistent_replay(self.model(), store)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["stored_confirmation_count"], 2)
            self.assertEqual(result["physical_actions_confirmed"], 0)
            self.assertEqual(store.overview(), before)
            finding = next(r for r in result["validated_results"] if r["inventory_id"] == "missing_code")
            self.assertEqual(finding["action_state"], "COMPLETED_CONFIRMED")
            self.assertEqual(finding["task"]["status"], "DONE")
            self.assertEqual(finding["task"]["remaining_quantity"], 0)
            self.assertNotIn("remains unconfirmed", finding["task"]["instruction"])

    def test_human_evidence_change_during_agent_run_invalidates_current_results(self):
        from pantry_recall.store import Store
        with TemporaryDirectory() as temp:
            store = Store(Path(temp) / "pantry.sqlite3")
            store.initialize()
            original_history = store.history

            def simultaneous_evidence(inventory_id):
                store.supply_evidence("missing_code", "synthetic-pantry-v2", "synthetic-pantry-v3",
                                      {"best_by_manufacturing_code": "BBD SEP 13 25 P"}, "synthetic-volunteer")
                return original_history(inventory_id)

            with patch.object(store, "history", side_effect=simultaneous_evidence):
                result = self.persistent_replay(self.model(), store)
            self.assertEqual(result["status"], "STALE_WORKFLOW_SNAPSHOT")
            self.assertEqual(result["validated_results"], [])
            self.assertEqual(len(result["stale_results"]), 8)
            self.assertEqual(store.case("missing_code")["identification_state"], "AFFECTED")
            self.assertEqual(store.case("missing_code")["action_state"], "HOLD_RECOMMENDED")

    def test_jif_adapter_executes_ten_rows_without_pearl_milling_prompt_assumptions(self):
        from pantry_recall.__main__ import score
        from pantry_recall.fixtures import DEFAULT_FIXTURE, read_json
        from pantry_recall.store import Store
        with TemporaryDirectory() as temp:
            fixture_path = DEFAULT_FIXTURE.parent / "jif_2022"
            store = Store(Path(temp) / "jif.sqlite3")
            store.initialize(fixture_path)
            result = self.persistent_replay(self.model(), store)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(len(result["validated_results"]), 10)
            self.assertEqual(score(result["validated_results"], read_json(fixture_path / "expected.json"))["failures"], [])
            self.assertEqual(result["physical_actions_confirmed"], 0)
            self.assertEqual(result["stored_confirmation_count"], 0)

    def test_failed_history_call_does_not_count_as_complete_tool_coverage(self):
        from pantry_recall.store import Store, WorkflowError
        with TemporaryDirectory() as temp:
            store = Store(Path(temp) / "pantry.sqlite3")
            store.initialize()
            with patch.object(store, "history", side_effect=WorkflowError("UNKNOWN_STOCK_GROUP", "Unknown group")):
                result = self.persistent_replay(self.model(), store, max_coverage_repairs=0)
            self.assertEqual(result["status"], "INCOMPLETE_TOOL_COVERAGE")
            self.assertIn("get_case_history", result["missing_tools"])

    def test_one_coverage_continuation_executes_tools_without_inventing_verdicts(self):
        fixture = load_fixture()
        ids = [row["inventory_id"] for row in fixture["inventory"]["rows"]]
        calls = [{"toolUse": {"toolUseId": f"repair-{i}", "name": name, "input": arguments}}
                 for i, (name, arguments) in enumerate([("load_recall_fixture", {}), ("load_inventory", {}),
                                                       ("find_candidates", {}), ("compare_scope", {"inventory_ids": ids})])]
        model = self.model()
        with Stubber(model.client) as stub:
            stub.add_response("converse", response([{"text": "Unsupported guess: missing-code stock is affected."}]))
            stub.add_response("converse", response(calls, "tool_use"))
            stub.add_response("converse", response([{"text": "Tool results now available."}]))
            result = run_agent(model, fixture)
            stub.assert_no_pending_responses()
        self.assertEqual(result["status"], "COMPLETE")
        self.assertEqual(len(result["coverage_repairs"]), 1)
        self.assertEqual(result["model_calls"], 3)
        self.assertEqual(result["usage"]["totalTokens"], 60)
        self.assertEqual(next(r for r in result["validated_results"] if r["inventory_id"] == "missing_code")["identification_state"], "NEEDS_EVIDENCE")


if __name__ == "__main__":
    unittest.main()
