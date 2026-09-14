import unittest
from tools import semeval_hybrid as h


class HybridTests(unittest.TestCase):
    def rows(self):
        return [{"": str(i), "title": f"food {i}", "text": text, "hazard-category": hazard, "product-category": "food",
                 "hazard": hazard, "product": "food"}
                for i, (text, hazard) in enumerate((("rice salmonella common", "bio"), ("rice bacteria common", "bio"),
                    ("rice migration chemical", "migration"), ("rice migration plastic", "migration"),
                    ("rice fungus recall", "bio"), ("rice migration plastic", "migration")))]

    def retriever(self):
        return h.BalancedRetriever(self.rows(), {"vectorizer": {"min_df": 1}, "title_weight": 0.7, "neighbors": 1,
            "example_characters": 2200, "hazard_example_characters": 900})

    def test_rare_category_and_duplicate_exclusion(self):
        target = {"title": "food 0", "text": "RICE  SALMONELLA COMMON"}
        examples = self.retriever().examples(target)
        self.assertEqual({e["hazard-category"] for e in examples}, {"bio", "migration"})
        bodies = [h.normalized_text(e["text"]) for e in examples]
        self.assertEqual(len(bodies), len(set(bodies)))
        self.assertNotIn(h.normalized_text(target["text"]), bodies)

    def test_target_labels_cannot_change_retrieval_or_request(self):
        retriever = self.retriever()
        target = {"title": "rice food", "text": "rice plastic", "hazard-category": "bogus", "product-category": "bogus"}
        a = retriever.examples(target)
        target.update({"hazard-category": "migration", "product-category": "food"})
        self.assertEqual(a, retriever.examples(target))
        p = {"model_id": "test", "system_prompt": "test", "tool_config": {}, "inference_config": {}}
        clean = {k: target[k] for k in ("title", "text")}
        self.assertEqual(h.request_for(target, p, a), h.request_for(clean, p, a))

    def test_hybrid_heads_and_margin_boundary(self):
        svm = {"prediction": dict(zip(h.FIELDS, ("s-h", "s-p"))), "margins": dict(zip(h.FIELDS, (1.0, .999)))}
        parent = dict(zip(h.FIELDS, ("p-h", "p-p")))
        self.assertEqual(list(h.combine(svm, parent, "both").values()), ["s-h", "s-p"])
        self.assertEqual(list(h.combine(svm, parent, "hazard").values()), ["s-h", "p-p"])
        self.assertEqual(list(h.combine(svm, parent, "product").values()), ["p-h", "s-p"])
        self.assertEqual(h.combine(svm, parent, "margin"), h.combine(svm, parent, "hazard"))
        self.assertEqual(parent[h.FIELDS[0]], "p-h")

    def test_supervised_inference_ignores_target_annotations(self):
        train = []
        for i, word in enumerate(("salmonella", "plastic", "milk")):
            for j in range(3):
                train.append({"": f"{i}-{j}", "title": word, "text": f"recall {word} food",
                              **{f: word for f in h.FIELDS}})
        classifier = h.TrainingClassifier(train, "balanced")
        target = {"": "target", "title": "salmonella", "text": "recall salmonella unseenmarker", **{f: "fake" for f in h.FIELDS}}
        first = classifier.predict([target])
        target.update({f: "plastic" for f in h.FIELDS})
        self.assertEqual(first, classifier.predict([target]))
        self.assertNotIn("unseenmarker", classifier.body.vocabulary_)
        self.assertEqual(set(first[0]["decision_scores"][h.FIELDS[0]]), {"salmonella", "plastic", "milk"})

    def test_selection_requires_strict_improvement(self):
        results = {v: {"official_st1_score": .8} for v in h.VARIANTS}
        self.assertEqual(h.select_best(results, {"official_st1_score": .8}), (h.VARIANTS[0], False))
        results[h.VARIANTS[-1]]["official_st1_score"] = .81
        self.assertEqual(h.select_best(results, {"official_st1_score": .8}), (h.VARIANTS[-1], True))


if __name__ == "__main__":
    unittest.main()
