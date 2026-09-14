import unittest
from tools.semeval_taxonomy import choose, taxonomy


class TaxonomyTests(unittest.TestCase):
    def test_full_taxonomy_keeps_rare_training_labels(self):
        train = [{"hazard-category": "biological", "hazard": "bacteria", "product-category": "bakery", "product": f"food {i}"} for i in range(12)]
        labels, guide = taxonomy(train)
        self.assertEqual(labels["product-category"], ["bakery"])
        self.assertEqual(set(guide["product-category"][0]["training_fine_labels"]), {f"food {i}" for i in range(12)})

    def test_conflicting_training_mappings_are_preserved_not_silently_resolved(self):
        train = [{"hazard-category": "allergens", "hazard": "milk", "product-category": category, "product": "bar"} for category in ("bakery", "snacks")]
        _, guide = taxonomy(train)
        self.assertEqual([r["training_fine_labels"] for r in guide["product-category"]], [["bar"], ["bar"]])

    def test_taxonomy_is_order_independent(self):
        train = [{"hazard-category": "allergens", "hazard": "milk", "product-category": "bakery", "product": name} for name in ("bread", "cake", "bread")]
        self.assertEqual(taxonomy(train), taxonomy(list(reversed(train))))


class CompositeSelectionTests(unittest.TestCase):
    incumbent = {"product_accuracy": .78, "hazard_accuracy": .94, "official_st1_score": .785}

    def result(self, product=.85, hazard=.95, score=.80, invalid=0):
        return {"product_accuracy": product, "hazard_accuracy": hazard, "official_st1_score": score, "invalid_outputs": invalid, "error_rows": 0}

    def test_composite_is_primary_even_when_accuracy_is_lower(self):
        results = {"pro-taxonomy": self.result(product=.75, hazard=.93, score=.82), "nova2-taxonomy": self.result(product=.90)}
        self.assertEqual(choose(results, self.incumbent), ("pro-taxonomy", True))

    def test_product_gain_cannot_hide_st1_decline(self):
        results = {"pro-taxonomy": self.result(product=.90, score=.78), "nova2-taxonomy": self.result(score=None)}
        self.assertEqual(choose(results, self.incumbent), ("pro-taxonomy", False))

    def test_equal_composite_does_not_authorize_test(self):
        results = {name: self.result(score=.785) for name in ("pro-taxonomy", "nova2-taxonomy")}
        self.assertEqual(choose(results, self.incumbent), ("pro-taxonomy", False))

    def test_selection_uses_unrounded_composite(self):
        results = {"pro-taxonomy": self.result(score=.85001), "nova2-taxonomy": self.result(score=.85002)}
        self.assertEqual(choose(results, self.incumbent), ("nova2-taxonomy", True))

    def test_ties_resolve_by_st1_then_invalid_outputs(self):
        results = {"pro-taxonomy": self.result(score=.82), "nova2-taxonomy": self.result()}
        self.assertEqual(choose(results, self.incumbent), ("pro-taxonomy", True))
        results = {"pro-taxonomy": self.result(invalid=1), "nova2-taxonomy": self.result()}
        self.assertEqual(choose(results, self.incumbent), ("nova2-taxonomy", True))
