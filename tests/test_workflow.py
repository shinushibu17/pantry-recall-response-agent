"""Policy-derived workflow expectations were frozen before this implementation."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from pantry_recall.confirmations import HoldConfirmation, record_human_confirmation
from pantry_recall.fixtures import DEFAULT_FIXTURE, digest
from pantry_recall.store import Store, WorkflowError
from pantry_recall.workflow import load_expectations, run_demo, stage_summary


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "pantry.sqlite3"
        self.store = Store(self.path)
        self.store.initialize()
        self.expected = load_expectations()

    def evidence(self, code="BBD SEP 13 25 P", base="synthetic-pantry-v2", version="synthetic-pantry-v3", **changes):
        return self.store.supply_evidence("missing_code", base, version,
                                           {"best_by_manufacturing_code": code, **changes}, "test-volunteer")

    def confirmation(self, quantity=2, inventory_id="missing_code", **changes):
        case = self.store.case(inventory_id)
        task = next(t for t in reversed(case["tasks"]) if t["inventory_version"] == case["inventory_version"])
        command = HoldConfirmation("test-confirmation-1", task["task_id"], inventory_id, case["inventory_version"],
                                   case["recall_version"], quantity, task["unit"], "test-volunteer",
                                   "Synthetic report: specified boxes isolated.", True)
        return replace(command, **changes)

    def assert_rejected(self, command, code):
        before = self.store.overview()
        with self.assertRaises(WorkflowError) as caught:
            record_human_confirmation(self.store, command)
        self.assertEqual(caught.exception.code, code)
        after = self.store.overview()
        self.assertEqual(before["cases"], after["cases"])
        self.assertEqual(before["confirmation_count"], after["confirmation_count"])
        self.assertEqual(after["event_count"], before["event_count"] + 1)
        with self.store.connection() as connection:
            event = connection.execute("SELECT * FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
            self.assertEqual(event["kind"], "COMMAND_REJECTED")
            self.assertEqual(json.loads(event["payload"])["code"], code)

    def test_frozen_four_stage_workflow_and_reopen(self):
        stages = [stage_summary(self.store.case("missing_code"), "initial")]
        case = self.evidence()
        stages.append(stage_summary(case, "evidence_arrived"))
        self.assertEqual(self.store.overview()["confirmation_count"], 0)
        command = self.confirmation()
        receipt = record_human_confirmation(self.store, command)
        stages.append(stage_summary(self.store.case("missing_code"), "partial_confirmation"))
        self.assertIn("policy.hold", receipt["evidence_refs"])
        self.assertNotIn("notice.consumer_instruction", receipt["evidence_refs"])
        self.assertEqual(receipt["location"], self.expected["location"])
        record_human_confirmation(self.store, replace(command, confirmation_id="test-confirmation-2"))
        reopened = Store(self.path)
        stages.append(stage_summary(reopened.case("missing_code"), "full_confirmation"))
        self.assertEqual(stages, self.expected["stages"])
        self.assertEqual(reopened.overview()["confirmation_count"], 2)
        self.assertEqual(reopened.case("missing_code")["scope_finding"]["identification_state"], "AFFECTED")
        self.assertEqual(reopened.case("affected")["action_state"], "HOLD_RECOMMENDED")

    def test_replays_do_not_reset_state_duplicate_tasks_or_quantity(self):
        original = self.store.overview()
        self.assertEqual(self.store.initialize(), original)
        self.evidence()
        command = self.confirmation()
        receipt = record_human_confirmation(self.store, command)
        before = self.store.overview()
        self.assertEqual(record_human_confirmation(self.store, command), receipt)
        self.evidence()
        self.store.initialize()
        fixture = self.store.load_context()
        results = self.store.evaluate([r["inventory_id"] for r in fixture["inventory"]["rows"]], fixture["inventory"]["version"], fixture["scope"]["version"])
        self.assertEqual(self.store.overview(), before)
        self.assertEqual(next(r for r in results if r["inventory_id"] == "missing_code")["action_state"], "AWAITING_CONFIRMATION")

    def test_inventory_versions_and_source_bytes_are_preserved(self):
        initial = self.store.inventory_version("synthetic-pantry-v2")
        untouched = {key: self.store.history(key) for key in ("unrelated", "affected", "excluded_code")}
        self.evidence()
        self.assertEqual(self.store.inventory_version("synthetic-pantry-v2"), initial)
        self.assertIsNone(next(r for r in initial["rows"] if r["inventory_id"] == "missing_code")["best_by_manufacturing_code"])
        self.assertEqual({key: self.store.history(key) for key in untouched}, untouched)
        with self.store.connection() as connection:
            sources = connection.execute("SELECT * FROM sources").fetchall()
            self.assertGreaterEqual(len(sources), 4)
            for source in sources:
                self.assertEqual(source["content"], (DEFAULT_FIXTURE / source["name"]).read_bytes())
                self.assertEqual(digest(source["content"]), source["sha256"])

    def test_stale_versions_wrong_group_unit_and_missing_attestation_are_audited(self):
        self.evidence()
        command = self.confirmation()
        for changes, code in [
            ({"inventory_version": "synthetic-pantry-v2"}, "STALE_INVENTORY_VERSION"),
            ({"recall_version": "old-recall"}, "STALE_RECALL_VERSION"),
            ({"inventory_id": "affected"}, "WRONG_STOCK_GROUP"),
            ({"inventory_id": "unknown"}, "UNKNOWN_STOCK_GROUP"),
            ({"task_id": "invented"}, "UNKNOWN_TASK"),
            ({"unit": "cases"}, "WRONG_UNIT"),
            ({"attest_isolated": False}, "ATTESTATION_REQUIRED"),
            ({"actor": ""}, "REQUIRED_CONFIRMATION_FIELD"),
        ]:
            with self.subTest(changes=changes):
                self.assert_rejected(replace(command, **changes), code)

    def test_invalid_and_excess_quantities_are_audited(self):
        self.evidence()
        command = self.confirmation()
        for quantity in (0, -1, True, 1.5, "2"):
            with self.subTest(quantity=quantity):
                self.assert_rejected(replace(command, quantity=quantity), "INVALID_QUANTITY")
        self.assert_rejected(replace(command, quantity=5), "EXCESS_QUANTITY")
        record_human_confirmation(self.store, command)
        self.assert_rejected(replace(command, confirmation_id="excess-remainder", quantity=3), "EXCESS_QUANTITY")

    def test_confirmation_id_conflict_and_completed_task_are_rejected(self):
        self.evidence()
        command = self.confirmation(quantity=4)
        receipt = record_human_confirmation(self.store, command)
        self.assert_rejected(replace(command, quantity=2), "CONFIRMATION_ID_CONFLICT")
        self.assert_rejected(replace(command, confirmation_id="another-receipt"), "TASK_NOT_OPEN")
        self.assertEqual(record_human_confirmation(self.store, command), receipt)

    def test_inspection_and_review_tasks_cannot_be_physically_confirmed(self):
        for inventory_id in ("missing_code", "excluded_code", "ambiguous_code"):
            with self.subTest(inventory_id=inventory_id):
                self.assert_rejected(self.confirmation(inventory_id=inventory_id), "INVALID_TRANSITION")

    def test_evidence_changes_preserve_receipts_and_supersede_open_hold(self):
        self.evidence()
        command = self.confirmation()
        receipt = record_human_confirmation(self.store, command)
        case = self.evidence(base="synthetic-pantry-v3", version="synthetic-pantry-v4", evidence_note="Synthetic second inspection of all labels.")
        old = next(t for t in case["tasks"] if t["task_id"] == command.task_id)
        new = next(t for t in case["tasks"] if t["inventory_version"] == "synthetic-pantry-v4")
        self.assertEqual((old["status"], old["confirmed_quantity"]), ("SUPERSEDED", 2))
        self.assertEqual((new["status"], new["confirmed_quantity"], new["remaining_quantity"]), ("OPEN", 0, 4))
        self.assertEqual(case["action_state"], "HOLD_RECOMMENDED")
        self.assert_rejected(replace(command, confirmation_id="stale-new-receipt"), "STALE_INVENTORY_VERSION")
        self.assertEqual(record_human_confirmation(self.store, command), receipt)

    def test_ambiguous_evidence_supersedes_inspection_without_completing_it(self):
        case = self.evidence("BBD 09/13/25 P")
        self.assertEqual(case["identification_state"], "NEEDS_REVIEW")
        self.assertEqual([(t["type"], t["status"]) for t in case["tasks"]], [("IDENTIFY_STOCK", "SUPERSEDED"), ("REVIEW_SCOPE", "OPEN")])

    def test_excluded_evidence_resolves_inspection_but_only_proposes_exclusion(self):
        case = self.evidence("BBD SEP 14 25 P")
        self.assertEqual((case["identification_state"], case["action_state"], case["proposed_identification_state"]),
                         ("NEEDS_REVIEW", "REVIEW_REQUIRED", "NOT_AFFECTED_BY_THIS_RECALL"))
        self.assertEqual([(t["type"], t["status"]) for t in case["tasks"]], [("IDENTIFY_STOCK", "DONE"), ("REVIEW_SCOPE", "OPEN")])
        self.assertIn("notice.other_products", case["tasks"][-1]["evidence_refs"])
        self.assertEqual(self.store.overview()["confirmation_count"], 0)

    def test_invalid_evidence_and_stale_updates_leave_no_partial_version(self):
        self.evidence()
        for code, base, version, expected in [
            ("BBD SEP 14 25 P", "synthetic-pantry-v2", "synthetic-pantry-v3", "VERSION_CONFLICT"),
            ("BBD SEP 13 25 P", "synthetic-pantry-v2", "synthetic-pantry-v4", "STALE_INVENTORY_VERSION"),
            (123, "synthetic-pantry-v3", "synthetic-pantry-v4", "INVALID_INVENTORY"),
        ]:
            before = self.store.overview()
            with self.assertRaises(WorkflowError) as caught:
                self.evidence(code, base, version)
            self.assertEqual(caught.exception.code, expected)
            after = self.store.overview()
            self.assertEqual(after["cases"], before["cases"])
            self.assertEqual(after["event_count"], before["event_count"] + 1)
        with self.assertRaises(WorkflowError):
            self.store.inventory_version("synthetic-pantry-v4")

    def test_stale_agent_snapshot_cannot_overwrite_new_evidence(self):
        self.evidence()
        before = self.store.overview()
        with self.assertRaises(WorkflowError) as caught:
            self.store.evaluate(["missing_code"], "synthetic-pantry-v2", "pearl-milling-2025-v2")
        self.assertEqual(caught.exception.code, "STALE_AGENT_SNAPSHOT")
        self.assertEqual(self.store.overview(), before)

    def test_evidence_and_events_are_append_only_in_sqlite(self):
        self.evidence()
        record_human_confirmation(self.store, self.confirmation())
        with self.store.connection() as connection:
            for table, column in [("events", "actor"), ("inventories", "actor"), ("recalls", "sha256"), ("sources", "sha256"), ("confirmations", "payload")]:
                for statement in (f"UPDATE {table} SET {column}='forged'", f"DELETE FROM {table}"):
                    with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                        connection.execute(statement)

    def test_concurrent_confirmations_cannot_exceed_stock_quantity(self):
        self.evidence()
        command = self.confirmation(quantity=3)

        def submit(number):
            try:
                return record_human_confirmation(self.store, replace(command, confirmation_id=f"concurrent-{number}"))["task_status"]
            except WorkflowError as error:
                return error.code

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(submit, [1, 2]))
        self.assertCountEqual(outcomes, ["OPEN", "EXCESS_QUANTITY"])
        case = self.store.case("missing_code")
        self.assertEqual(case["tasks"][-1]["confirmed_quantity"], 3)
        self.assertEqual(case["tasks"][-1]["remaining_quantity"], 1)
        self.assertEqual(self.store.overview()["confirmation_count"], 1)

    def test_full_demo_and_replay_are_idempotent(self):
        first = run_demo(self.store)
        self.assertEqual(first["status"], "PASS")
        self.assertEqual(len(first["checks"]), 4)
        before = self.store.overview()
        replay = run_demo(Store(self.path))
        self.assertEqual(replay["status"], "PASS")
        self.assertFalse(replay["fresh_replay"])
        self.assertEqual(replay["checks"], [])
        self.assertEqual(first["receipts"], replay["receipts"])
        self.assertEqual(self.store.overview(), before)


if __name__ == "__main__":
    unittest.main()
