import importlib.util
import json
import unittest
from tools.semeval_product import TrainingRetriever, request_for, target_hash


class TitleInputTests(unittest.TestCase):
    def test_target_title_is_included_but_answers_and_other_metadata_are_not(self):
        row={"title":"Named product","text":"Recall details","product":"SECRET_ANSWER","hazard":"SECRET_ANSWER","product-category":"SECRET_ANSWER","country":"SECRET_METADATA"}
        protocol={"model_id":"test","system_prompt":"test","tool_config":{},"inference_config":{}}
        payload=json.dumps(request_for(row,protocol,[]))
        self.assertIn("Named product",payload)
        self.assertNotIn("SECRET",payload)

    def test_input_binding_changes_when_title_changes(self):
        self.assertNotEqual(target_hash({"title":"wine","text":"same body"}),target_hash({"title":"juice","text":"same body"}))


@unittest.skipUnless(importlib.util.find_spec("sklearn"),"Evaluation dependencies required")
class TitleRetrievalTests(unittest.TestCase):
    def train(self):
        return [{"":"0","title":"wine red grape","text":"one shared recall text","product":"wine","hazard":"glass","product-category":"drinks","hazard-category":"foreign bodies"},
                {"":"1","title":"salmon fish seafood","text":"two shared recall text","product":"salmon","hazard":"listeria","product-category":"fish","hazard-category":"biological"}]

    def test_title_ranking_and_training_fine_labels(self):
        config={"neighbors":1,"example_characters":2200,"title_weight":1.0,"vectorizer":{"ngram_range":[1,2]}}
        result=TrainingRetriever(self.train(),config).examples({"title":"salmon fish seafood","text":"shared recall query","product":"DO_NOT_USE"})
        self.assertEqual(result[0]["training_id"],"1")
        self.assertEqual(result[0]["annotated_product"],"salmon")
        self.assertNotIn("DO_NOT_USE",json.dumps(result))

    def test_same_target_text_excluded_even_with_different_title(self):
        config={"neighbors":2,"example_characters":2200,"title_weight":0.7,"vectorizer":{}}
        result=TrainingRetriever(self.train(),config).examples({"title":"wine red grape","text":"one shared recall text"})
        self.assertNotIn("0",[row["training_id"] for row in result])
