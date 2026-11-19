"""Validate contrasts, unavailable values and independent measurement runs."""
import copy
import unittest

from sonification_stimuli.endpoint_report import build_dataset, percentage
from sonification_stimuli.endpoints import CONDITIONS, DIMENSIONS


def sample_rows(batch="one", backend="native-cpython"):
    rows = []
    for target, level in sorted(CONDITIONS):
        rows.append({"batch_id": batch, "created_at_utc": "2026-11-03T00:00:00Z",
                     "target_characteristic": target, "condition_level": str(level),
                     "input_mode": "source", "base_label": "example", "analysis_backend": backend,
                     "assumed_reference_spl_db": "60", "f0_hz": "200",
                     "f0_hz_status": "ok", "loudness_sone": "2", "roughness_asper": "0",
                     "steady_rms_dbfs": "-20", "target_operation_active": "false" if target == "pulsation" else "true"})
    return rows


class EndpointReportTests(unittest.TestCase):
    def test_signed_changes_raw_values_and_zero_reference(self):
        rows = sample_rows()
        low = next(row for row in rows if row["target_characteristic"] == "pitch" and row["condition_level"] == "1")
        high = next(row for row in rows if row["target_characteristic"] == "pitch" and row["condition_level"] == "5")
        low.update(f0_hz="100", loudness_sone="1", steady_rms_dbfs="-23")
        high.update(f0_hz="300", roughness_asper=".1")
        dataset, tidy = build_dataset(rows)
        self.assertEqual(len(tidy), 60)
        pitch = next(cell for cell in tidy if cell["target"] == "pitch" and cell["metric"] == "f0_hz")
        self.assertEqual((pitch["reference"], pitch["delta_1"], pitch["percent_1"], pitch["contrast_5_minus_1"]), (200, -100, -50, 200))
        rms = next(cell for cell in tidy if cell["target"] == "pitch" and cell["metric"] == "steady_rms_dbfs")
        self.assertEqual(rms["delta_1"], -3)
        self.assertIsNone(rms["percent_1"])
        roughness = next(cell for cell in tidy if cell["target"] == "pitch" and cell["metric"] == "roughness_asper")
        self.assertEqual(roughness["delta_5"], .1)
        self.assertIsNone(roughness["percent_5"])
        rate = next(cell for cell in tidy if cell["target"] == "pulsation")
        self.assertFalse(rate["active_1"])

    def test_missing_estimates_never_become_zero_or_percentages(self):
        rows = sample_rows()
        row = next(row for row in rows if row["target_characteristic"] == "pitch" and row["condition_level"] == "1")
        row.update(f0_hz="0", f0_hz_status="unavailable", f0_hz_reason="weak periodicity")
        _, tidy = build_dataset(rows)
        cell = next(cell for cell in tidy if cell["target"] == "pitch" and cell["metric"] == "f0_hz")
        self.assertIsNone(cell["level_1"])
        self.assertIsNone(cell["delta_1"])
        self.assertIsNone(cell["percent_1"])
        self.assertEqual(cell["reason_1"], "weak periodicity")
        self.assertIsNone(percentage(1, 0, "ratio"))

    def test_runs_stay_separate_and_mixed_calibration_is_rejected(self):
        rows = sample_rows() + sample_rows("two", "browser-pyodide")
        data, _ = build_dataset(rows)
        self.assertEqual(len(data["sets"]), 2)
        self.assertNotEqual(data["sets"][0]["id"], data["sets"][1]["id"])
        rows[0]["assumed_reference_spl_db"] = "65"
        with self.assertRaisesRegex(ValueError, "mixes"):
            build_dataset(rows)


if __name__ == "__main__":
    unittest.main()
