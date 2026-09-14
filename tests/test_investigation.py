"""Authored expectations for task choice, changing evidence, and briefing authority."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pantry_recall.confirmations import HoldConfirmation, record_human_confirmation
from pantry_recall.investigation import Investigation
from pantry_recall.store import Store, WorkflowError


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name)/"pantry.sqlite3")
        self.store.initialize()
        self.baseline = self.store.overview()["event_count"]

    def investigator(self, since=None):
        fixture = self.store.load_context()
        result = Investigation(self.store, fixture, self.store.overview(),
                               {"kind":"workflow_change", "since_event": self.baseline if since is None else since})
        result.work_queue()
        return result

    def ids(self):
        return [r["inventory_id"] for r in self.store.load_context()["inventory"]["rows"]]

    def choose(self, inv, stock):
        task = next(t for t in inv.queue["open_tasks"] if t["inventory_id"]==stock)
        inv.history(stock)
        return task

    def evidence(self):
        return self.store.supply_evidence("missing_code", "synthetic-pantry-v2", "inspected-v3",
                                         {"best_by_manufacturing_code":"BBD SEP 13 25 P"}, "Synthetic reviewer")

    def confirm(self, case, identifier, quantity=2):
        task = next(t for t in case["tasks"] if t["type"]=="PERFORM_ACTION" and t["status"]=="OPEN")
        return record_human_confirmation(self.store, HoldConfirmation(identifier, task["task_id"], "missing_code",
            case["inventory_version"], case["recall_version"], quantity, "boxes", "Synthetic reviewer", "Simulated hold", True))

    def test_model_can_select_a_different_case_without_a_forced_missing_code_history(self):
        inv = self.investigator()
        task = self.choose(inv,"mixed_codes")
        result = inv.submit([task["task_id"]],[task["evidence_refs"][0]],["Inspect the mixed donation group."],self.ids())
        self.assertEqual(result["history_inspected"],["mixed_codes"])
        self.assertEqual(result["priorities"][0]["task"]["quantity"],9)
        self.assertEqual(self.store.overview()["event_count"],self.baseline)
        self.assertEqual(self.store.overview()["confirmation_count"],0)

    def test_change_report_uses_stored_before_and_after_evidence(self):
        self.evidence()
        inv = self.investigator()
        change = inv.queue["changes"][0]
        self.assertEqual(change["field_changes"]["best_by_manufacturing_code"], {"before":None,"after":"BBD SEP 13 25 P"})
        task = self.choose(inv,"missing_code")
        self.assertEqual(task["type"],"PERFORM_ACTION")
        self.assertEqual(task["remaining_quantity"],4)
        brief=inv.submit([task["task_id"]],["policy.hold"],["New evidence resolves identification; the hold remains open."],self.ids())
        self.assertEqual(brief["physical_actions_confirmed"],0)

    def test_case_context_preserves_unknowns_and_exact_source_bindings(self):
        inv = self.investigator()
        context = inv.history("missing_code")["decision_context"]
        self.assertIsNone(context["stock"]["best_by_manufacturing_code"])
        self.assertEqual(context["stock"]["product_name"], "Original Pancake & Waffle Mix")
        self.assertEqual(context["source_evidence"]["notice.product_table"], inv.fixture["scope"]["evidence"]["notice.product_table"])
        self.assertIn("BBD SEP 13 25 P", context["source_evidence"]["notice.product_table"]["quote"])
        self.assertEqual(context["policy_evidence"]["policy.hold"], inv.fixture["policy"]["evidence"]["policy.hold"])
        self.assertEqual(context["unresolved_evidence_refs"], [])
        context["stock"]["best_by_manufacturing_code"] = "invented"
        context["source_evidence"]["notice.product_table"]["quote"] = "invented"
        reread = inv.history("missing_code")["decision_context"]
        self.assertIsNone(reread["stock"]["best_by_manufacturing_code"])
        self.assertNotEqual(reread["source_evidence"]["notice.product_table"]["quote"], "invented")
        self.assertEqual(self.store.overview()["event_count"], self.baseline)

    def test_case_context_uses_revised_stock_and_retains_missing_reference(self):
        self.evidence()
        inv = self.investigator()
        del inv.fixture["scope"]["evidence"]["notice.product_table"]
        context = inv.history("missing_code")["decision_context"]
        self.assertEqual(context["stock"]["best_by_manufacturing_code"], "BBD SEP 13 25 P")
        self.assertIn("notice.product_table", context["unresolved_evidence_refs"])

    def test_partial_receipt_changes_remaining_quantity_and_done_hold_is_ineligible(self):
        case=self.evidence()
        self.confirm(case,"first-two")
        inv=self.investigator()
        task=self.choose(inv,"missing_code")
        self.assertEqual(task["remaining_quantity"],2)
        self.assertEqual(inv.queue["changes"][-1]["kind"],"HOLD_CONFIRMED")
        self.confirm(self.store.case("missing_code"),"other-two")
        finished=self.investigator()
        finished.history("missing_code")
        with self.assertRaisesRegex(ValueError,"OPEN task"):
            finished.submit([task["task_id"]],["policy.hold"],["Repeat a completed action"],self.ids())
        other=self.choose(finished,"mixed_codes")
        finished.submit([other["task_id"]],[other["evidence_refs"][0]],["Continue with the remaining mixed group."],self.ids())
        self.assertEqual(self.store.overview()["confirmation_count"],2)

    def test_history_citation_coverage_and_changed_case_are_required(self):
        self.evidence()
        inv=self.investigator()
        task=self.choose(inv,"affected")
        with self.assertRaisesRegex(ValueError,"changed stock"):
            inv.submit([task["task_id"]],["policy.hold"],["Hold stock"],self.ids())
        inv.history("missing_code")
        with self.assertRaisesRegex(ValueError,"changed stock"):
            inv.submit([task["task_id"]],["policy.hold"],["Ignore the change"],self.ids())
        task=self.choose(inv,"missing_code")
        with self.assertRaisesRegex(ValueError,"evidence ID"):
            inv.submit([task["task_id"]],["invented-source"],["Fictional citation"],self.ids())
        with self.assertRaisesRegex(ValueError,"every stock"):
            inv.submit([task["task_id"]],["policy.hold"],["Incomplete comparisons"],["missing_code"])
        self.assertIsNone(inv.briefing)

    def test_missing_non_candidate_is_named_in_tool_feedback(self):
        inv=self.investigator()
        task=self.choose(inv,"missing_code")
        with self.assertRaisesRegex(ValueError,'missing IDs, including non-candidates: \\["unrelated"\\]'):
            inv.submit([task["task_id"]],["policy.hold"],["Inspect the missing code"],set(self.ids())-{"unrelated"})

    def test_feedback_reports_all_actionable_submission_problems_together(self):
        self.evidence()
        inv=self.investigator()
        queue=inv.work_queue()
        task=next(t for t in queue["open_tasks"] if t["inventory_id"]=="mixed_codes")
        with self.assertRaises(ValueError) as error:
            inv.submit([task["task_id"]],["invented-citation"],["Inspect stock"],set(self.ids())-{"unrelated"})
        feedback=str(error.exception)
        for required in ('unrelated','missing_code','mixed_codes','evidence ID','REPLACE one selection'):
            self.assertIn(required,feedback)
        self.assertIsNone(inv.briefing)

    def test_evidence_change_invalidates_prepared_plan(self):
        inv=self.investigator()
        task=self.choose(inv,"missing_code")
        self.evidence()
        with self.assertRaises(WorkflowError) as error:
            inv.submit([task["task_id"]],["policy.hold"],["Old evidence"],self.ids())
        self.assertEqual(error.exception.code,"STALE_AGENT_SNAPSHOT")


from tests.test_agent import HAS_STRANDS
if HAS_STRANDS:
    from botocore.stub import Stubber
    from tests import test_agent as agent_tests
    from pantry_recall.agent import run_agent


@unittest.skipUnless(HAS_STRANDS,"Install locked Strands dependencies")
class AdaptiveSDKTests(unittest.TestCase):
    def test_serial_recovery_can_finish_after_twelfth_tool_call(self):
        # Reproduce the Nova Pro completed-hold failure: premature submissions,
        # late changed-stock history, and candidate discovery in the last tool call.
        from pantry_recall.workflow import run_demo
        with TemporaryDirectory() as temp:
            store = Store(Path(temp)/"serial-recovery.sqlite3")
            run_demo(store)
            fixture = store.load_context()
            inv = Investigation(store, fixture, store.overview(), {"kind": "workflow_change", "since_event": 0})
            queue = inv.work_queue()
            selected = [next(t for t in queue["open_tasks"] if t["inventory_id"] == key)
                        for key in ("affected", "excluded_code", "mixed_codes")]
            submission = {"task_ids": [t["task_id"] for t in selected], "reasons": ["Continue the stored open work."]*3}
            calls = [("load_recall_fixture", {}), ("load_inventory", {}),
                     ("compare_scope", {"inventory_ids": [r["inventory_id"] for r in fixture["inventory"]["rows"]]}),
                     ("get_work_queue", {}), ("submit_briefing", submission),
                     ("get_case_history", {"inventory_id": "affected"}),
                     ("get_case_history", {"inventory_id": "excluded_code"}),
                     ("get_case_history", {"inventory_id": "mixed_codes"}),
                     ("submit_briefing", submission),
                     ("get_case_history", {"inventory_id": "missing_code"}),
                     ("submit_briefing", submission), ("find_candidates", {})]
            model = agent_tests.AgentIntegrationTests.model(self)
            with Stubber(model.client) as stub:
                for index, (name, arguments) in enumerate(calls):
                    stub.add_response("converse", agent_tests.response([{"toolUse": {
                        "toolUseId": "serial-"+str(index), "name": name, "input": arguments}}], "tool_use"))
                stub.add_response("converse", agent_tests.response([{"text": "Stored work reviewed; human receipts unchanged."}]))
                report = run_agent(model, fixture, store=store, investigate=True,
                                   trigger={"kind": "workflow_change", "since_event": 0})
                stub.assert_no_pending_responses()
            self.assertEqual(report["status"], "COMPLETE")
            self.assertEqual(report["model_calls"], 13)
            self.assertEqual(report["stored_confirmation_count"], 2)
            self.assertEqual(report["physical_actions_confirmed"], 0)
            self.assertEqual(report["execution_limits"], {"model_calls": 16, "tool_calls": 20})

    def test_failed_browser_selection_uses_stored_citations_without_model_retyping(self):
        from pantry_recall.agent import build_tools, RunTrace
        from pantry_recall.investigation import Investigation
        with TemporaryDirectory() as temp:
            store=Store(Path(temp)/"citation-regression.sqlite3");store.initialize()
            fixture=store.load_context()
            inv=Investigation(store,fixture,store.overview(),None)
            trace=RunTrace()
            tools={t.tool_name:t for t in build_tools(fixture,trace,store,inv)}
            schema=tools["submit_briefing"].tool_spec["inputSchema"]["json"]
            self.assertEqual(set(schema["properties"]),{"task_ids","reasons"})
            queue=tools["get_work_queue"]()
            tools["compare_scope"](inventory_ids=[r["inventory_id"] for r in fixture["inventory"]["rows"]])
            keys=["missing_code","mixed_codes","ambiguous_code"]
            selected=[next(t for t in queue["open_tasks"] if t["inventory_id"]==key) for key in keys]
            for key in keys:tools["get_case_history"](inventory_id=key)
            ids=[t["task_id"] for t in selected]
            reasons=["Inspect missing code.","Inspect the mixed group.","Review the ambiguous transcription."]
            # The exact field-suffix pattern from the failed public browser run
            # still fails the original evidence validator; it is never repaired.
            with self.assertRaisesRegex(ValueError,"evidence ID"):
                inv.submit(ids,[f"inventory:synthetic-pantry-v2:{key}#best_by_manufacturing_code" for key in keys],reasons,trace.results)
            briefing=tools["submit_briefing"](task_ids=ids,reasons=reasons)
            for proposed,task in zip(briefing["priorities"],selected):
                self.assertEqual(proposed["task"],task)
                self.assertEqual(proposed["cited_evidence_ids"],task["evidence_refs"])
                self.assertEqual(proposed["evidence_binding"],"stored_task")
            self.assertEqual(store.overview()["confirmation_count"],0)

    def test_automatic_evidence_binding_cannot_resolve_an_unknown_task(self):
        from pantry_recall.investigation import Investigation
        with TemporaryDirectory() as temp:
            store=Store(Path(temp)/"unknown.sqlite3");store.initialize()
            fixture=store.load_context()
            inv=Investigation(store,fixture,store.overview(),None)
            inv.work_queue()
            with self.assertRaisesRegex(ValueError,"existing OPEN task"):
                inv.submit_selected(["invented-task"],["Fabricated work"],[r["inventory_id"] for r in fixture["inventory"]["rows"]])
            self.assertIsNone(inv.briefing)

    def test_model_failure_preserves_partial_tool_execution_without_a_briefing(self):
        with TemporaryDirectory() as temp:
            store=Store(Path(temp)/"failed.sqlite3");store.initialize()
            fixture=store.load_context()
            model=agent_tests.AgentIntegrationTests.model(self)
            with Stubber(model.client) as stub:
                stub.add_response("converse",agent_tests.response([
                    {"toolUse":{"toolUseId":"loaded","name":"load_inventory","input":{}}}
                ],"tool_use"))
                stub.add_client_error("converse",service_error_code="ModelErrorException",service_message="Invalid tool-use sequence",http_status_code=424)
                result=run_agent(model,fixture,store=store,investigate=True)
                stub.assert_no_pending_responses()
            self.assertEqual(result["status"],"FAILED")
            self.assertEqual(result["tool_calls"],[{"tool":"load_inventory","arguments":{}}])
            self.assertEqual(result["model_calls"],2)
            self.assertEqual(result["failure"]["aws_error_code"],"ModelErrorException")
            self.assertEqual(result["failure"]["status"],"MODEL_OUTPUT_ERROR")
            self.assertIsNone(result["briefing"])
            self.assertFalse(result["usage_complete"])
            self.assertEqual(store.overview()["confirmation_count"],0)

    def test_real_sdk_selects_cases_and_publishes_source_bound_plan(self):
        with TemporaryDirectory() as temp:
            store=Store(Path(temp)/"agent.sqlite3");store.initialize()
            fixture=store.load_context()
            selections=[store.case(key)["tasks"][-1] for key in ("mixed_codes","contradictory_label")]
            groups=[[("load_recall_fixture",{}),("load_inventory",{}),("find_candidates",{}),
                     ("compare_scope",{"inventory_ids":[r["inventory_id"] for r in fixture["inventory"]["rows"]]}),("get_work_queue",{})],
                    [("get_case_history",{"inventory_id":key}) for key in ("mixed_codes","contradictory_label")],
                    [("submit_briefing",{"task_ids":[t["task_id"] for t in selections],
                                          "reasons":["Nine units need group inspection.","The label evidence conflicts."]})]]
            model=agent_tests.AgentIntegrationTests.model(self)
            with Stubber(model.client) as stub:
                for n,group in enumerate(groups):
                    calls=[{"toolUse":{"toolUseId":f"step-{n}-{i}","name":name,"input":args}} for i,(name,args) in enumerate(group)]
                    stub.add_response("converse",agent_tests.response(calls,"tool_use"))
                stub.add_response("converse",agent_tests.response([{"text":"Advisory work plan ready."}]))
                result=run_agent(model,fixture,store=store,investigate=True)
                stub.assert_no_pending_responses()
            self.assertEqual(result["status"],"COMPLETE")
            self.assertEqual(result["briefing"]["history_inspected"],["contradictory_label","mixed_codes"])
            self.assertEqual(len(result["validated_results"]),8)
            self.assertEqual(store.overview()["confirmation_count"],0)
