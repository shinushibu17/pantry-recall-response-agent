"""Synthetic benchmark harness tests, independent of released test answers."""
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.semeval_eval import make_prompt, parse_prediction, read_rows, request_for, official_score, classify

CATEGORIES = {"hazard-category": ["biological", "allergens"], "product-category": ["dairy", "nuts"]}


class SemEvalBoundaryTests(unittest.TestCase):
    def test_inference_payload_never_contains_test_labels_or_metadata(self):
        row = {"text": "Synthetic food report", "title": "SECRET_TITLE", "hazard-category": "SECRET_ANSWER", "product-category": "SECRET_ANSWER", "country": "SECRET_COUNTRY"}
        request = request_for(row, {"model_id": "test", "system_prompt": make_prompt(CATEGORIES), "inference_config": {}})
        self.assertNotIn("SECRET", json.dumps(request))
        self.assertEqual(json.loads(request["messages"][0]["content"][0]["text"]), {"report_text": row["text"]})

    def test_valid_json_and_single_fence(self):
        value = {"hazard-category": "biological", "product-category": "dairy"}
        for text in (json.dumps(value), "```json\n" + json.dumps(value) + "\n```"):
            self.assertEqual(parse_prediction(text, CATEGORIES), value)

    def test_unknown_label_and_extra_fields_rejected(self):
        for value in ({"hazard-category": "Biological", "product-category": "dairy"},
                      {"hazard-category": "biological", "product-category": "dairy", "action": "release"},
                      {"hazard-category": [], "product-category": "dairy"}):
            with self.assertRaises(ValueError):
                parse_prediction(json.dumps(value), CATEGORIES)

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(ValueError):
            parse_prediction('{"hazard-category":"allergens","hazard-category":"biological","product-category":"dairy"}', CATEGORIES)

    def test_duplicate_dataset_ids_rejected(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "data.csv"
            path.write_text(',title,text,hazard-category,product-category\n0,t,a,b,c\n0,t,a,b,c\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_rows(path)

    def test_empty_full_text_rejected(self):
        with TemporaryDirectory() as temp:
            path = Path(temp) / "data.csv"
            path.write_text(',title,text,hazard-category,product-category\n0,title,,b,c\n', encoding="utf-8")
            with self.assertRaises(ValueError):
                read_rows(path)

    def test_malformed_output_is_preserved_without_retry_and_resume_makes_no_call(self):
        class Client:
            calls = 0
            def converse(self, **kwargs):
                self.calls += 1
                return {"output": {"message": {"content": [{"text": "bad output"}]}}, "stopReason": "end_turn"}
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            lock = directory / "protocol.json"
            lock.write_text("{}", encoding="utf-8")
            client = Client()
            row = {"": "0", "text": "synthetic report"}
            protocol = {"model_id": "test", "system_prompt": "test", "inference_config": {}, "categories": CATEGORIES}
            with patch("tools.semeval_eval.PROTOCOL", lock):
                first = classify(client, row, protocol, directory)
                resumed = classify(client, row, protocol, directory)
                self.assertEqual(first["status"], "INVALID_OUTPUT")
                self.assertEqual(len(first["attempts"]), 1)
                self.assertEqual(client.calls, 1)
                self.assertTrue(resumed["_cached"])
                with self.assertRaises(ValueError):
                    classify(client, {**row, "text": "changed"}, protocol, directory)


@unittest.skipUnless(importlib.util.find_spec("sklearn"), "Install evaluation dependencies with uv sync --group evaluation")
class SemEvalScoringTests(unittest.TestCase):
    def test_perfect_score(self):
        import numpy as np
        h, p = np.array(["a", "b"]), np.array(["x", "y"])
        self.assertEqual(official_score(h, p, h, p), 1.0)

    def test_product_score_is_conditional_on_correct_hazard(self):
        import numpy as np
        # Hazard macro F1=(2/3+0)/2=1/3; conditional product F1=1.
        # The wrong product on the hazard-wrong row must not enter product F1.
        result = official_score(np.array(["a", "b"]), np.array(["x", "y"]),
                                np.array(["a", "a"]), np.array(["x", "wrong"]))
        self.assertAlmostEqual(result, 2 / 3)
