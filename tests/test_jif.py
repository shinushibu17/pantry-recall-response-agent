"""Jif source-adapter regression tests; not a blind deterministic held-out score."""

from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pantry_recall.__main__ import score
from pantry_recall.fixtures import DEFAULT_FIXTURE, FixtureError, load_fixture, read_json
from pantry_recall.jif import lot_truth, validate_jif_instructions
from pantry_recall.matching import evaluate_inventory
from pantry_recall.store import Store
from pantry_recall.workflow import main as workflow_main


JIF = DEFAULT_FIXTURE.parent / "jif_2022"


class JifTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_fixture(JIF)

    def test_all_ten_frozen_reference_outcomes(self):
        report = score(evaluate_inventory(self.fixture), read_json(JIF / "expected.json"))
        self.assertEqual(report["passed"], 10, report["failures"])
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["split"], "agent-held-out")
        self.assertEqual(report["incorrect_exclusion_proposals"], 0)
        self.assertEqual(report["candidate_retrieval_misses"], 0)

    def test_seven_digit_positions_are_not_a_full_number_interval(self):
        rule = self.fixture["scope"]["variant"]["lot_rule"]
        self.assertEqual(lot_truth("21404259999", rule)[0], "true")
        self.assertEqual(lot_truth("2000426", rule)[0], "false")
        for raw in ["200O425", "2000425 ", "200042", "２０００４２５", "lot 2000425"]:
            with self.subTest(raw=raw):
                self.assertEqual(lot_truth(raw, rule)[0], "unknown")

    def test_supported_subset_does_not_exclude_another_recalled_variant(self):
        row = next(r for r in evaluate_inventory(self.fixture) if r["inventory_id"] == "other_recalled_variant")
        self.assertEqual(row["identification_state"], "NEEDS_REVIEW")
        self.assertIsNone(row["proposed_identification_state"])
        self.assertIn("CRUNCHY", self.fixture["scope"]["evidence"]["notice.other_recalled_variant"]["quote"])

    def test_enforcement_date_aggregation_is_not_an_unmapped_exclusion_window(self):
        fixture = deepcopy(self.fixture)
        fixture["inventory"]["rows"] = [fixture["inventory"]["rows"][0]]
        fixture["inventory"]["rows"][0]["best_by_date"] = "2026-01-01"
        finding = evaluate_inventory(fixture)[0]
        self.assertEqual(finding["identification_state"], "AFFECTED")
        self.assertNotIn("best_by_date", finding["conditions"])

    def test_altered_source_predicate_requires_review(self):
        fixture = deepcopy(self.fixture)
        fixture["scope"]["variant"]["lot_rule"]["following_digits"] = "426"
        findings = evaluate_inventory(fixture)
        self.assertTrue(all(r["identification_state"] == "NEEDS_REVIEW" for r in findings if r["candidate"]["included"]))
        self.assertTrue(all(r["proposed_identification_state"] is None for r in findings))

    def test_conditional_cleaning_and_company_disposal_keep_distinct_attribution(self):
        instructions = self.fixture["scope"]["instructions"]
        self.assertEqual([i["issuer"] for i in instructions], ["The J. M. Smucker Co.", "FDA", "FDA"])
        self.assertIn("was used", instructions[2]["trigger"])
        for field, value in [("trigger", "Always"), ("issuer", "The J. M. Smucker Co."), ("action", "Discard all pantry inventory")]:
            scope = deepcopy(self.fixture["scope"])
            scope["instructions"][2][field] = value
            with self.subTest(field=field), self.assertRaises(FixtureError):
                validate_jif_instructions(scope)

    def test_every_judgment_points_to_stored_source_or_inventory_evidence(self):
        for finding in evaluate_inventory(self.fixture):
            refs = list(finding["candidate"]["evidence_refs"])
            refs += finding.get("context_evidence_refs", [])
            if finding["task"]:
                refs += finding["task"]["evidence_refs"]
            for condition in finding["conditions"].values():
                refs += condition["evidence_refs"]
            for ref in refs:
                self.assertTrue(ref in self.fixture["scope"]["evidence"] or ref in self.fixture["policy"]["evidence"] or ref.startswith(f"inventory:synthetic-jif-v1:{finding['inventory_id']}"), ref)

    def test_lot_evidence_cli_resolves_identification_without_confirming_action(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "jif.sqlite3"
            store = Store(path)
            store.initialize(JIF)
            with redirect_stdout(StringIO()):
                status = workflow_main(["--db", str(path), "evidence", "--inventory-id", "missing_lot", "--expected-version", "synthetic-jif-v1", "--new-version", "synthetic-jif-v2", "--lot-code", "2000425", "--actor", "synthetic-volunteer", "--note", "Synthetic inspection of all four jars."])
            self.assertEqual(status, 0)
            case = store.case("missing_lot")
            self.assertEqual((case["identification_state"], case["action_state"]), ("AFFECTED", "HOLD_RECOMMENDED"))
            self.assertEqual([(t["type"], t["status"]) for t in case["tasks"]], [("IDENTIFY_STOCK", "DONE"), ("PERFORM_ACTION", "OPEN")])
            self.assertEqual(store.overview()["confirmation_count"], 0)
            self.assertIsNone(store.inventory_version("synthetic-jif-v1")["rows"][5]["lot_code"])
            self.assertIn("sources/investigation.txt", [r[0] for r in self._source_names(store)])

    @staticmethod
    def _source_names(store):
        with store.connection() as connection:
            return connection.execute("SELECT name FROM sources").fetchall()


if __name__ == "__main__":
    unittest.main()
