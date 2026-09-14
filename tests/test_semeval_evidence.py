import unittest
from unittest.mock import patch
from datetime import datetime, timezone
from tempfile import TemporaryDirectory
from pathlib import Path
from tools import semeval_evidence as v


class EvidenceTests(unittest.TestCase):
    labels = {v.FIELDS[0]: ["bio", "other"], v.FIELDS[1]: ["rice", "other"]}

    def response(self, **changes):
        values = {"product_description": "rice", "hazard_description": "salmonella", "hazard_id": 0, "product_id": 0, **changes}
        return {"stopReason": "tool_use", "output": {"message": {"content": [
            {"reasoningContent": {"reasoningText": {"text": "[REDACTED]"}}},
            {"toolUse": {"name": "classify_incident", "input": values}}]}}}

    def test_valid_evidence_and_redacted_reasoning(self):
        self.assertEqual(v.parse_tool(self.response(), self.labels), {v.FIELDS[0]: "bio", v.FIELDS[1]: "rice"})

    def test_schema_rejects_malformed_evidence_and_ids(self):
        for change in ({"product_description": " "}, {"hazard_description": "x"*501}, {"hazard_description": None}, {"hazard_id": True}, {"product_id": "0"}, {"extra": 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                v.parse_tool(self.response(**change), self.labels)

    def test_no_target_answers_in_reasoning_request(self):
        p = {"model_id": "test", "system_prompt": "test", "tool_config": v.evidence_tool_config(self.labels), "inference_config": {"maxTokens":4096},
            "additional_model_request_fields": {"reasoningConfig":{"type":"enabled","maxReasoningEffort":"low"}}}
        target = {"title":"rice", "text":"salmonella recall", **{f:"secret gold" for f in v.FIELDS}}
        a = v.request_for(target, p, [])
        self.assertEqual(a, v.request_for({k:target[k] for k in ("title","text")}, p, []))
        self.assertEqual(a["additionalModelRequestFields"], p["additional_model_request_fields"])

    def test_small_validation_gain_does_not_authorize_test(self):
        r = {name:{"official_st1_score":.8001} for name in v.VARIANTS}
        self.assertFalse(v.choose(r, {"official_st1_score":.8})[1])
        r[v.VARIANTS[1]]["official_st1_score"] = .81
        self.assertEqual(v.choose(r, {"official_st1_score":.8}), (v.VARIANTS[1], True))

    def test_cutoff_prevents_calls(self):
        class Client:
            def converse(self, **kwargs):
                raise AssertionError("Must not call after user cutoff")
        p = {"model_id":"test", "system_prompt":"test", "tool_config":{}, "inference_config":{}, "labels":self.labels}
        row = {"":"1", "title":"rice", "text":"recall"}
        with TemporaryDirectory() as temp, patch.object(v, "CUTOFF", datetime(2000,1,1,tzinfo=timezone.utc)):
            record = v.classify(Client(), row, p, "hash", [], Path(temp))
        self.assertTrue(record["cutoff_reached"])
        self.assertEqual(record["attempts"], [])
        self.assertEqual(record["status"], "ERROR")


if __name__ == "__main__":
    unittest.main()
