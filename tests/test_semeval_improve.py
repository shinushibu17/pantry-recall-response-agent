import importlib.util
import json
import unittest
from tools.semeval_improve import parse_tool, request_for, taxonomy, tool_config, TrainingRetriever

LABELS = {"hazard-category": ["a", "b"], "product-category": ["x", "y"]}


def response(value):
    return {"stopReason": "tool_use", "output": {"message": {"content": [{"toolUse": {"name": "classify_incident", "input": value}}]}}}


class StructuredCategoryTests(unittest.TestCase):
    def test_valid_ids_map_exactly_to_frozen_categories(self):
        self.assertEqual(parse_tool(response({"hazard_id": 1, "product_id": 0}), LABELS), {"hazard-category": "b", "product-category": "x"})

    def test_strings_booleans_out_of_range_and_extra_fields_rejected(self):
        for value in ({"hazard_id": "1", "product_id": 0}, {"hazard_id": True, "product_id": 0},
                      {"hazard_id": -1, "product_id": 0}, {"hazard_id": 2, "product_id": 0},
                      {"hazard_id": 1, "product_id": 0, "release": True}):
            with self.assertRaises(ValueError):
                parse_tool(response(value), LABELS)

    def test_missing_or_multiple_tools_rejected(self):
        for content in ([], [response({})["output"]["message"]["content"][0]] * 2):
            with self.assertRaises(ValueError):
                parse_tool({"stopReason": "tool_use", "output": {"message": {"content": content}}}, LABELS)

    def test_request_omits_target_labels_and_metadata(self):
        protocol = {"model_id": "test", "system_prompt": "test", "tool_config": tool_config(LABELS), "inference_config": {}}
        row = {"text": "synthetic input", "title": "SECRET_TITLE", "hazard-category": "SECRET_ANSWER", "product-category": "SECRET_ANSWER"}
        self.assertNotIn("SECRET", json.dumps(request_for(row, protocol, [])))

    def test_taxonomy_uses_only_supplied_training_rows(self):
        train = [{"hazard-category": "a", "product-category": "x", "hazard": "training hazard", "product": "training product"}]
        labels, guidance = taxonomy(train)
        self.assertEqual(labels, {"hazard-category": ["a"], "product-category": ["x"]})
        self.assertEqual(guidance["hazard-category"][0]["training_fine_labels"], ["training hazard"])


@unittest.skipUnless(importlib.util.find_spec("sklearn"), "Evaluation dependencies required")
class TrainingRetrievalTests(unittest.TestCase):
    def test_exact_target_and_duplicate_training_text_excluded(self):
        train = [{"": str(i), "text": text, "hazard-category": "a", "product-category": "x"} for i, text in enumerate([
            "milk recall salmonella", "milk recall bacteria", "milk recall bacteria", "milk recalled contamination"])]
        config = {"neighbors": 4, "example_characters": 2200, "vectorizer": {"ngram_range": [1, 2]}}
        examples = TrainingRetriever(train, config).examples(" MILK recall salmonella ")
        self.assertNotIn("0", [e["training_id"] for e in examples])
        self.assertEqual(len(examples), 2)
