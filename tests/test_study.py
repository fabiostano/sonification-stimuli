from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile as sf

from sonification_stimuli.study import conditions, generate, render, rms, StimulusConfig


SPEC = Path(__file__).resolve().parents[1] / "configs" / "exploratory_set.json"


class StudyTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads(SPEC.read_text())
        self.spec["carrier"].update(duration_s=3.0, fade_s=0.5)

    def test_exactly_one_control_changes_per_condition(self):
        entries = conditions(self.spec)
        self.assertEqual(len(entries), 21)
        self.assertEqual(len({row[0] for row in entries}), 21)
        reference = asdict(entries[0][3])
        for _, _, _, config in entries[1:]:
            current = asdict(config)
            changes = sum(current[k] != reference[k] for k in current if k != "carrier")
            changes += sum(current["carrier"][k] != reference["carrier"][k] for k in current["carrier"])
            self.assertEqual(changes, 1)

    def test_energy_hnr_endpoints_and_seed(self):
        config = conditions(self.spec)[0][3]
        x, diagnostics = render(config)
        self.assertEqual(x.shape, (144000,))
        self.assertEqual(x[0], 0)
        self.assertEqual(x[-1], 0)
        self.assertTrue(np.isfinite(x).all())
        self.assertLess(np.max(abs(x)), 1)
        self.assertAlmostEqual(rms(x[24000:-24000]), config.carrier.gain / np.sqrt(2), places=12)
        self.assertAlmostEqual(diagnostics["source_hnr_db"], config.hnr_db, places=10)
        np.testing.assert_array_equal(x, render(config)[0])
        self.assertFalse(np.array_equal(x, render(replace(config, noise_seed=8))[0]))

    def test_measured_am_sidebands(self):
        config = replace(conditions(self.spec)[0][3], hnr_db=120.0, roughness_depth=0.4)
        x, _ = render(config)
        steady = x[24000:-24000]  # Exactly 2 seconds, integer cycles for all test rates.
        amplitudes = abs(np.fft.rfft(steady))
        f = np.fft.rfftfreq(steady.size, 1 / config.carrier.sample_rate)
        at = lambda hz: amplitudes[np.argmin(abs(f - hz))]
        for sign in (-1, 1):
            self.assertAlmostEqual(at(220 + sign * 70) / at(220), 0.4 / 2, places=6)
            self.assertAlmostEqual(at(220 + sign * 2) / at(220), 0.25 / 2, places=6)

    def test_invalid_sets(self):
        self.spec["levels"]["pitch"][0] = 300
        with self.assertRaises(ValueError):
            conditions(self.spec)
        config = StimulusConfig()
        for updates in ({"roughness_depth": 1.1}, {"hnr_db": float("nan")},
                        {"noise_high_hz": 25000}, {"pulsation_hz": 0}):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                render(replace(config, **updates))

    def test_complete_export_and_shared_reference_previews(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            rows = generate(self.spec, output, make_plots=False)
            self.assertEqual(len(rows), 21)
            self.assertEqual(len(list(output.glob("*.wav"))), 21)
            self.assertEqual(len({row["sha256_wav"] for row in rows}), 21)
            reference, fs = sf.read(output / "reference.wav")
            timing = json.loads((output / "previews" / "timing.json").read_text())
            for dimension, segments in timing.items():
                preview, preview_fs = sf.read(output / "previews" / f"{dimension}.wav")
                self.assertEqual(preview_fs, fs)
                segment = segments[2]
                self.assertEqual(segment["id"], "reference")
                np.testing.assert_array_equal(preview[round(segment["start_s"] * fs):round(segment["end_s"] * fs)], reference)
            for row in rows:
                wav = output / row["wav"]
                self.assertEqual(hashlib.sha256(wav.read_bytes()).hexdigest(), row["sha256_wav"])
                self.assertEqual(sf.info(wav).subtype, "PCM_24")
            with self.assertRaises(ValueError):
                generate(self.spec, output, make_plots=False)


if __name__ == "__main__":
    unittest.main()
