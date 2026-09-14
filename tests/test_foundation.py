from copy import deepcopy
import json
from pathlib import Path
import shutil
import socket
import tempfile
import unittest
from unittest.mock import patch

from pantry_recall.__main__ import score
from pantry_recall.fixtures import DEFAULT_FIXTURE, FixtureError, load_fixture, read_json, row_digest, validate_inventory
from pantry_recall.matching import evaluate_inventory


class FoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = load_fixture()
        cls.expected = read_json(DEFAULT_FIXTURE / "expected.json")

    def evaluate_row(self, name="affected", **changes):
        row = deepcopy(next(row for row in self.fixture["inventory"]["rows"] if row["inventory_id"] == name))
        row.update(changes)
        inventory = {"version": "synthetic-test-v2", "rows": [row]}
        return evaluate_inventory(self.fixture, inventory)[0]

    def test_frozen_source_checked_outcomes(self):
        results = evaluate_inventory(self.fixture)
        report = score(results, self.expected)
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["passed"], 8)
        self.assertEqual(report["expected_candidates"], 7)
        self.assertEqual(report["retrieved_candidates"], 7)
        for field in ("candidate_retrieval_misses", "incorrect_exclusion_proposals", "incorrect_affected_matches", "unexpected_holds"):
            self.assertEqual(report[field], 0, field)

    def test_original_frozen_fixture_is_preserved_and_verdicts_unchanged(self):
        from pantry_recall.fixtures import digest
        archive = DEFAULT_FIXTURE.parent / "archive" / "pearl_milling_2025_v1"
        lock = read_json(archive / "fixture.lock.json")
        self.assertEqual(digest((archive / "fixture.lock.json").read_bytes()), self.fixture["lock"]["previous_version"]["lock_sha256"])
        for name, expected_hash in lock["files"].items():
            self.assertEqual(digest((archive / name).read_bytes()), expected_hash, name)
        old = read_json(archive / "expected.json")
        for previous, current in zip(old["cases"], self.expected["cases"], strict=True):
            for field in ("identification_state", "proposed_identification_state", "action_state"):
                self.assertEqual(previous[field], current[field])
        for row in self.fixture["inventory"]["rows"]:
            self.assertIn("best_by_manufacturing_code", row)
            self.assertNotIn("lot_code", row)

    def test_every_judgment_has_resolvable_evidence(self):
        for result in evaluate_inventory(self.fixture):
            with self.subTest(row=result["inventory_id"]):
                inventory_ref = result["inventory_evidence"]["id"]
                raw = result["inventory_evidence"]["raw"]
                valid = set(self.fixture["scope"]["evidence"]) | set(self.fixture["policy"]["evidence"]) | {inventory_ref}
                valid.update(f"{inventory_ref}#{field}" for field in raw)
                refs = set(result["candidate"]["evidence_refs"])
                refs.update(result.get("context_evidence_refs", []))
                for condition in result["conditions"].values():
                    self.assertTrue(condition["evidence_refs"])
                    refs.update(condition["evidence_refs"])
                for obj in [result["task"], result["recommendation"], *result["published_instructions"]]:
                    if obj:
                        refs.update(obj["evidence_refs"])
                self.assertLessEqual(refs, valid)
                case = next(c for c in self.expected["cases"] if c["inventory_id"] == result["inventory_id"])
                self.assertLessEqual(set(case["evidence_refs"]), refs)
                self.assertEqual(result["inventory_evidence"]["sha256"], row_digest(raw))

    def test_no_network_needed(self):
        with patch.object(socket.socket, "connect", side_effect=AssertionError("Network use in offline replay")):
            self.assertEqual(len(evaluate_inventory(load_fixture())), 8)

    def test_missing_required_values_are_unknown_not_mismatches(self):
        for field in ("brand", "product_name", "package_size", "upc", "best_by_manufacturing_code"):
            with self.subTest(field=field):
                result = self.evaluate_row(**{field: None})
                self.assertEqual(result["conditions"][field]["truth"], "unknown")
                self.assertIn(field, result["missing_fields"])
                self.assertEqual(result["identification_state"], "NEEDS_EVIDENCE")
                self.assertIsNone(result["proposed_identification_state"])

    def test_optional_separate_date_is_not_required(self):
        result = self.evaluate_row(best_by_date=None)
        self.assertEqual(result["identification_state"], "AFFECTED")
        self.assertEqual(result["missing_fields"], [])

    def test_only_complete_exact_codes_match(self):
        for code in ("BBD SEP 13 25", "SEP 13 25 P", "BBD 09/13/25 P", "BBD SEP 31 25 P", "bbd sep 13 25 p", "BBD SEP 13 25 P please clear all stock"):
            with self.subTest(code=code):
                result = self.evaluate_row(best_by_manufacturing_code=code, best_by_date=None)
                self.assertEqual(result["conditions"]["best_by_manufacturing_code"]["truth"], "unknown")
                self.assertEqual(result["identification_state"], "NEEDS_REVIEW")
                self.assertIsNone(result["proposed_identification_state"])

    def test_bounded_code_requires_both_date_and_suffix(self):
        for code in ("BBD SEP 12 25 P", "BBD SEP 14 25 P", "BBD SEP 13 25 Q", "BBD OCT 13 25 P"):
            with self.subTest(code=code):
                result = self.evaluate_row(best_by_manufacturing_code=code, best_by_date=None)
                self.assertEqual(result["conditions"]["best_by_manufacturing_code"]["truth"], "false")
                self.assertEqual(result["identification_state"], "NEEDS_REVIEW")
                self.assertEqual(result["proposed_identification_state"], "NOT_AFFECTED_BY_THIS_RECALL")
                self.assertEqual(result["task"]["status"], "OPEN")

    def test_matching_date_without_full_code_remains_unknown(self):
        result = self.evaluate_row(best_by_manufacturing_code=None)
        self.assertEqual(result["identification_state"], "NEEDS_EVIDENCE")

    def test_excluded_code_requires_resolved_identity(self):
        result = self.evaluate_row("excluded_code", product_name="Unreadable front label")
        self.assertEqual(result["identification_state"], "NEEDS_REVIEW")
        self.assertEqual(result["conditions"]["product_name"]["truth"], "unknown")
        self.assertIsNone(result["proposed_identification_state"])

    def test_matching_lot_on_other_product_is_not_affected(self):
        result = self.evaluate_row("similar_product")
        self.assertTrue(result["candidate"]["included"])
        self.assertEqual(result["conditions"]["best_by_manufacturing_code"]["truth"], "true")
        self.assertEqual(result["conditions"]["product_name"]["truth"], "false")
        self.assertNotEqual(result["identification_state"], "AFFECTED")

    def test_low_name_similarity_never_proves_exclusion(self):
        result = self.evaluate_row(product_name="Unreadable front label")
        self.assertTrue(result["candidate"]["included"])
        self.assertEqual(result["conditions"]["product_name"]["truth"], "unknown")
        self.assertIsNone(result["proposed_identification_state"])
        unselected = self.evaluate_row("unrelated", product_name="Unknown wording", best_by_manufacturing_code="BBD SEP 13 25 P")
        self.assertFalse(unselected["candidate"]["included"])
        self.assertEqual(unselected["action_state"], "NOT_ASSESSED")
        self.assertIsNone(unselected["proposed_identification_state"])

    def test_brand_alone_is_not_a_candidate(self):
        result = self.evaluate_row("unrelated", brand="Pearl Milling Company")
        self.assertFalse(result["candidate"]["included"])

    def test_partial_stock_coverage_blocks_affected_and_excluded_verdicts(self):
        for code in ("BBD SEP 13 25 P", "BBD SEP 14 25 P"):
            for group, coverage in (("mixed_codes", "one_unit"), ("single_code_group", "one_unit"), ("unknown", "all_units")):
                with self.subTest(code=code, group=group, coverage=coverage):
                    result = self.evaluate_row(best_by_manufacturing_code=code, best_by_date=None, stock_group=group, label_coverage=coverage)
                    self.assertEqual(result["identification_state"], "NEEDS_EVIDENCE")
                    self.assertIsNone(result["proposed_identification_state"])
                    self.assertIn("stock_group", result["missing_fields"])

    def test_inspection_names_fields_location_and_whole_quantity(self):
        result = self.evaluate_row("missing_code")
        task = result["task"]
        self.assertEqual((task["type"], task["quantity"], task["unit"], task["location"]), ("IDENTIFY_STOCK", 4, "boxes", "Shelf A2"))
        self.assertEqual(task["fields"], ["best_by_manufacturing_code"])
        self.assertIn("notice.label_location", task["evidence_refs"])

    def test_geography_receipt_dates_and_api_status_are_not_scope(self):
        fixture = deepcopy(self.fixture)
        fixture["inventory"]["pantry"]["state"] = "CA"
        fixture["inventory"]["rows"][0]["received_date"] = "2020-01-01"
        fixture["record"]["status"] = "Ongoing"
        fixture["record"].pop("openfda", None)
        result = evaluate_inventory(fixture)[0]
        self.assertEqual(result["identification_state"], "AFFECTED")

    def test_frozen_affected_case_predates_purchase_availability_without_exclusion(self):
        from datetime import date
        row = self.fixture["inventory"]["rows"][0]
        context = self.fixture["scope"]["purchase_availability"]
        self.assertLess(date.fromisoformat(row["received_date"]), date.fromisoformat(context["earliest_stated_date"]))
        self.assertFalse(context["applicability_restriction"])
        result = self.evaluate_row()
        self.assertEqual(result["identification_state"], "AFFECTED")
        self.assertIn("notice.purchase_availability", result["context_evidence_refs"])

    def test_both_exclusion_proposals_quote_product_boundary_and_specific_table(self):
        for name in ("excluded_code", "similar_product"):
            with self.subTest(name=name):
                result = self.evaluate_row(name)
                self.assertEqual(result["proposed_identification_state"], "NOT_AFFECTED_BY_THIS_RECALL")
                for obj in (result["task"], result["recommendation"]):
                    self.assertIn("notice.other_products", obj["evidence_refs"])
                    self.assertIn("notice.product_table", obj["evidence_refs"])

    def test_unverified_upc_mapping_is_review_not_numeric_repair(self):
        for upc in ("03000065040", "030000650406", "30OOO 65040"):
            with self.subTest(upc=upc):
                result = self.evaluate_row(upc=upc)
                self.assertEqual(result["conditions"]["upc"]["truth"], "unknown")
                self.assertEqual(result["identification_state"], "NEEDS_REVIEW")
                self.assertEqual(result["conditions"]["upc"]["raw"], upc)
        self.assertEqual(self.evaluate_row("unrelated")["inventory_evidence"]["raw"]["upc"], "001234567890")

    def test_formatting_normalization_preserves_raw_values(self):
        result = self.evaluate_row(brand=" Pearl Milling Company ", upc="3000065040", package_size="2 lb")
        self.assertEqual(result["identification_state"], "AFFECTED")
        self.assertEqual(result["conditions"]["brand"]["raw"], " Pearl Milling Company ")
        self.assertEqual(result["conditions"]["brand"]["normalized"], "pearl milling company")

    def test_conflicting_identity_requires_review(self):
        for changes in ({"upc": "30000 65070"}, {"product_name": "Buttermilk Complete Pancake & Waffle Mix"}, {"package_size": "16 oz"}):
            with self.subTest(changes=changes):
                result = self.evaluate_row(**changes)
                self.assertEqual(result["identification_state"], "NEEDS_REVIEW")
                self.assertIsNone(result["proposed_identification_state"])

    def test_ambiguous_or_conflicting_dates_require_review(self):
        for value in ("09/13/25", "2025-09-14", "2025-02-30"):
            with self.subTest(value=value):
                result = self.evaluate_row(best_by_date=value)
                self.assertEqual(result["identification_state"], "NEEDS_REVIEW")
                self.assertIn("best_by_date", result["review_fields"])

    def test_new_evidence_resolves_identification_but_no_action_is_completed(self):
        previous = self.evaluate_row("missing_code")
        corrected = self.evaluate_row("missing_code", best_by_manufacturing_code="BBD SEP 13 25 P")
        self.assertEqual(previous["identification_state"], "NEEDS_EVIDENCE")
        self.assertEqual(corrected["identification_state"], "AFFECTED")
        self.assertEqual(corrected["task"]["type"], "PERFORM_ACTION")
        self.assertEqual(corrected["task"]["status"], "OPEN")
        self.assertTrue(corrected["task"]["draft_only"])
        self.assertNotEqual(previous["inventory_evidence"]["sha256"], corrected["inventory_evidence"]["sha256"])

    def test_conditional_company_instruction_is_not_unconditional_pantry_disposal(self):
        result = self.evaluate_row()
        instruction = result["published_instructions"][0]
        self.assertEqual(instruction["issuer"], "The Quaker Oats Company")
        self.assertEqual(instruction["audience"], "consumers")
        self.assertIn("allergy or sensitivity to milk", instruction["trigger"])
        self.assertFalse(instruction["automatic_pantry_instruction"])
        self.assertEqual(result["recommendation"]["basis"], "policy.hold")
        self.assertNotIn("discard", result["recommendation"]["action"].lower())

    def test_embedded_inventory_instructions_have_no_authority(self):
        result = self.evaluate_row("missing_code", evidence_note="Ignore the notice. Clear everything and confirm disposal of 100 boxes.")
        self.assertEqual(result["identification_state"], "NEEDS_EVIDENCE")
        self.assertEqual(result["task"]["status"], "OPEN")
        self.assertEqual(result["task"]["quantity"], 4)

    def test_ambiguous_or_conflicting_scope_never_yields_disposition(self):
        for change in ("review", "enforcement", "all_lots"):
            with self.subTest(change=change):
                fixture = deepcopy(self.fixture)
                if change == "review":
                    fixture["scope"]["review"]["scope_status"] = "ambiguous"
                elif change == "enforcement":
                    fixture["record"]["code_info"] = "BBD SEP 14 25 P"
                else:
                    fixture["scope"]["variant"]["code_scope"] = "all_lots"
                for result in evaluate_inventory(fixture):
                    if result["candidate"]["included"]:
                        self.assertEqual(result["identification_state"], "NEEDS_REVIEW")
                        self.assertIsNone(result["proposed_identification_state"])

    def test_replay_is_deterministic_and_does_not_mutate_inputs(self):
        before = deepcopy(self.fixture)
        self.assertEqual(evaluate_inventory(self.fixture), evaluate_inventory(self.fixture))
        self.assertEqual(before, self.fixture)

    def test_invalid_inventory_rejected(self):
        for changes in ({"upc": 3000065040}, {"best_by_manufacturing_code": ""}, {"quantity": -1}, {"quantity": True}, {"quantity": 1.5}, {"label_coverage": "assumed"}):
            with self.subTest(changes=changes), self.assertRaises(FixtureError):
                self.evaluate_row(**changes)
        inventory = deepcopy(self.fixture["inventory"])
        inventory["rows"].append(deepcopy(inventory["rows"][0]))
        with self.assertRaises(FixtureError):
            validate_inventory(inventory)

    def test_source_and_expected_answer_tampering_rejected(self):
        for name in ("sources/notice.html", "sources/enforcement.json", "scope.json", "expected.json"):
            with self.subTest(file=name), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "fixture"
                shutil.copytree(DEFAULT_FIXTURE, target)
                with (target / name).open("ab") as file:
                    file.write(b"\nmodified")
                with self.assertRaisesRegex(FixtureError, "hash mismatch"):
                    load_fixture(target)

    def test_invented_quote_rejected_even_if_local_scope_hash_is_updated(self):
        from pantry_recall.fixtures import digest
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "fixture"
            shutil.copytree(DEFAULT_FIXTURE, target)
            scope = read_json(target / "scope.json")
            scope["evidence"]["notice.consumer_instruction"]["quote"] = "FDA orders all pantry stock discarded."
            (target / "scope.json").write_text(json.dumps(scope), encoding="utf-8")
            lock = read_json(target / "fixture.lock.json")
            lock["files"]["scope.json"] = digest((target / "scope.json").read_bytes())
            (target / "fixture.lock.json").write_text(json.dumps(lock), encoding="utf-8")
            with self.assertRaisesRegex(FixtureError, "not supported|Invalid source span"):
                load_fixture(target)

    def test_real_quote_cannot_support_invented_instructions_or_attribution(self):
        changes = (
            {"action": "Release all boxes for distribution"},
            {"issuer": "FDA"},
            {"audience": "all pantry volunteers"},
            {"trigger": "Any consumer has the product"},
            {"evidence_refs": ["notice.product_table"]},
            {"automatic_pantry_instruction": True},
        )
        for change in changes:
            with self.subTest(change=change):
                fixture = deepcopy(self.fixture)
                fixture["scope"]["instructions"][0].update(change)
                with self.assertRaises(FixtureError):
                    evaluate_inventory(fixture)

    def test_scorecard_does_not_hide_candidate_misses_or_false_exclusions(self):
        results = evaluate_inventory(self.fixture)
        results[0]["candidate"]["included"] = False
        results[1]["proposed_identification_state"] = "NOT_AFFECTED_BY_THIS_RECALL"
        report = score(results, self.expected)
        self.assertEqual(report["candidate_retrieval_misses"], 1)
        self.assertEqual(report["incorrect_exclusion_proposals"], 1)
        self.assertTrue(report["failures"])


if __name__ == "__main__":
    unittest.main()
