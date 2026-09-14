import copy
import unittest

from tools.semeval_capacity import candidates, choose


class CapacitySelectionTests(unittest.TestCase):
    def scores(self, lite, pro, lite_invalid=0, pro_invalid=0):
        return {
            "lite-eight": {"official_st1_score": lite, "invalid_outputs": lite_invalid, "error_rows": 0},
            "pro-four": {"official_st1_score": pro, "invalid_outputs": pro_invalid, "error_rows": 0},
        }

    def test_no_test_run_when_neither_candidate_beats_incumbent(self):
        self.assertEqual(choose(self.scores(.70, .72), .73), ("pro-four", False))

    def test_equal_incumbent_is_not_improvement(self):
        self.assertEqual(choose(self.scores(.73, .72), .73), ("lite-eight", False))

    def test_strict_winner_uses_unrounded_score(self):
        self.assertEqual(choose(self.scores(.73111, .73112), .73), ("pro-four", True))

    def test_ties_prefer_fewer_invalid_outputs_then_lite(self):
        self.assertEqual(choose(self.scores(.75, .75, 1, 0), .73), ("pro-four", True))
        self.assertEqual(choose(self.scores(.75, .75), .73), ("lite-eight", True))

    def test_missing_scores_cannot_promote(self):
        self.assertEqual(choose(self.scores(None, None), .73), ("lite-eight", False))

    def test_candidate_changes_are_isolated_and_do_not_mutate_incumbent(self):
        incumbent = {"model_id": "amazon.nova-lite-v1:0", "retrieval": {"neighbors": 4, "title_weight": .7},
                     "system_prompt": "unchanged", "inference_config": {"temperature": 0}}
        before = copy.deepcopy(incumbent)
        configs = candidates(incumbent)
        self.assertEqual(incumbent, before)
        for name, config in configs.items():
            self.assertEqual(config["system_prompt"], before["system_prompt"])
            self.assertEqual(config["inference_config"], before["inference_config"])
            self.assertEqual(config["retrieval"]["title_weight"], .7)
            self.assertEqual(config["retrieval"]["neighbors"], 8 if name == "lite-eight" else 4)
            self.assertEqual(config["model_id"], "amazon.nova-lite-v1:0" if name == "lite-eight" else "amazon.nova-pro-v1:0")
        configs["lite-eight"]["retrieval"]["title_weight"] = 0
        self.assertEqual(configs["pro-four"]["retrieval"]["title_weight"], .7)
