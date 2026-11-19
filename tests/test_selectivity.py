"""Analytical examples for target rewards, coupling, missingness and cohort scales."""
import copy
import math
import unittest

from sonification_stimuli.selectivity import PROXIES, LOUDNESS, calculate_control, evaluate_cohort, build_selectivity


def base():
    cells = [{"target": target, "metric": metric, "reference": 1., "level_1": 1., "level_5": 1.,
              "active_1": True, "active_5": True} for target in PROXIES for metric in [*PROXIES.values(), LOUDNESS]]
    return {"id": "test", "label": "Test", "mode": "drone", "created": "now", "backend": "native", "spl": 60, "cells": cells}


class SelectivityTests(unittest.TestCase):
    def test_known_benefit_no_change_and_reversal(self):
        item = base()
        scales = {key: 2 for key in [*PROXIES.values(), LOUDNESS]}
        cell = next(c for c in item["cells"] if c["target"] == "pitch" and c["metric"] == PROXIES["pitch"])
        cell.update(level_1=0, level_5=2)
        result = calculate_control(item, "pitch", list(PROXIES), scales)
        self.assertEqual(result["benefit"], .5)
        self.assertEqual(result["coupling"], 0)
        self.assertEqual(result["score"], .5)
        cell.update(level_1=2, level_5=0)
        result = calculate_control(item, "pitch", list(PROXIES), scales)
        self.assertEqual(result["score"], -.5)
        self.assertFalse(result["ordered"])
        zero = evaluate_cohort([base()], list(PROXIES), scales)["bases"][0]
        self.assertEqual(zero["score"], 0)

    def test_opposite_coupling_does_not_cancel_and_loudness_is_penalized(self):
        item = base()
        scales = {key: 2 for key in [*PROXIES.values(), LOUDNESS]}
        cell = next(c for c in item["cells"] if c["target"] == "pitch" and c["metric"] == LOUDNESS)
        cell.update(level_1=0, level_5=2)
        result = calculate_control(item, "pitch", list(PROXIES), scales)
        self.assertGreater(result["coupling"], 0)
        self.assertAlmostEqual(result["coupling"], .5 / math.sqrt(5))
        self.assertLess(result["score"], 0)

    def test_common_basis_and_strict_missing_coverage(self):
        first, second = base(), base()
        second["id"] = "second"
        for cell in second["cells"]:
            if cell["metric"] == PROXIES["pitch"]:
                cell["level_1"] = None
        cohort = build_selectivity({"sets": [first, second]})["cohorts"][0]
        self.assertNotIn("pitch", cohort["common"]["targets"])
        self.assertTrue(all(item["available"] for item in cohort["common"]["bases"]))
        self.assertFalse(cohort["full"]["bases"][1]["available"])
        self.assertIsNone(cohort["full"]["bases"][1]["score"])

    def test_unit_rescaling_does_not_change_scores_and_cohorts_stay_separate(self):
        item = base()
        next(c for c in item["cells"] if c["target"] == "pitch" and c["metric"] == PROXIES["pitch"])["level_5"] = 2
        original = build_selectivity({"sets": [item]})["cohorts"][0]["full"]["bases"][0]["score"]
        changed = copy.deepcopy(item)
        for cell in changed["cells"]:
            if cell["metric"] == PROXIES["pitch"]:
                for key in ("reference", "level_1", "level_5"):
                    cell[key] *= 1000
        result = build_selectivity({"sets": [changed]})["cohorts"][0]["full"]["bases"][0]["score"]
        self.assertAlmostEqual(original, result)
        changed["backend"] = "browser"
        self.assertEqual(len(build_selectivity({"sets": [item, changed]})["cohorts"]), 2)

    def test_pulsation_controls_share_one_domain_and_all_zero_data_is_finite(self):
        item = base()
        scales = {key: 2 for key in [*PROXIES.values(), LOUDNESS]}
        for target in ("pulsation", "pulse_depth"):
            next(cell for cell in item["cells"] if cell["target"] == target and cell["metric"] == PROXIES[target]).update(level_1=0, level_5=2)
        self.assertAlmostEqual(evaluate_cohort([item], list(PROXIES), scales)["bases"][0]["score"], .1)
        for cell in item["cells"]:
            cell.update(reference=0, level_1=0, level_5=0)
        result = build_selectivity({"sets": [item]})["cohorts"][0]
        self.assertTrue(all(value == 1 for value in result["scales"].values()))
        self.assertEqual(result["full"]["bases"][0]["score"], 0)


if __name__ == "__main__":
    unittest.main()
