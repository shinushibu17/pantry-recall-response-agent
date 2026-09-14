import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from tools import semeval_ensemble as v


class EnsembleTests(unittest.TestCase):
    labels = {v.FIELDS[0]: ["bio", "allergen"], v.FIELDS[1]: ["rice", "milk"]}

    def record(self, h="bio", p="rice", status="VALID"):
        return {"id":"1", "input_sha256":"target", "prediction":dict(zip(v.FIELDS,(h,p))),"status":status}

    def test_selected_heads_are_combined_without_mutating_parents(self):
        left, right = self.record("allergen","rice"), self.record("bio","milk")
        pred, status = v.combine_records(left,right,self.labels)
        self.assertEqual(pred,dict(zip(v.FIELDS,("allergen","milk"))))
        self.assertEqual(status,"VALID")
        self.assertEqual(left["prediction"][v.FIELDS[1]],"rice")

    def test_cross_target_and_incomplete_outputs_cannot_be_laundered(self):
        wrong = self.record();wrong["input_sha256"]="different"
        with self.assertRaises(ValueError):v.combine_records(self.record(),wrong,self.labels)
        pred,status=v.combine_records(self.record(),self.record(v.INVALID,v.INVALID,"ERROR"),self.labels)
        self.assertEqual(status,"ERROR")
        self.assertEqual(set(pred.values()),{v.INVALID})

    def test_gain_threshold_and_tie_order(self):
        names=[v.combo_name(*pair) for pair in v.COMBINATIONS]
        results={name:{"official_st1_score":.804} for name in names}
        self.assertEqual(v.choose(results,{"official_st1_score":.8}),(names[0],False))
        results[names[-1]]["official_st1_score"] = .81
        self.assertEqual(v.choose(results,{"official_st1_score":.8}),(names[-1],True))

    def test_cutoff_prevents_model_calls(self):
        class Client:
            def converse(self,**kwargs):raise AssertionError("Model invoked after cutoff")
        p={"model_id":"test","system_prompt":"test","tool_config":{},"inference_config":{},"labels":self.labels}
        with TemporaryDirectory() as temp,patch.object(v,"CUTOFF",datetime(2000,1,1,tzinfo=timezone.utc)):
            record=v.classify(Client(),{"":"1","title":"rice","text":"recall"},p,"hash",[],Path(temp))
        self.assertEqual(record["attempts"],[])
        self.assertTrue(record["cutoff_reached"])


if __name__ == "__main__":unittest.main()
