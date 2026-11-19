"""Scientific invariants and export integration; run with unittest."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import soundfile as sf

from sonification_stimuli import DroneConfig, synthesize
from sonification_stimuli.synthesis import partials


class SynthesisTests(unittest.TestCase):
    def setUp(self):
        self.config = DroneConfig(duration_s=2, fade_s=0.25)

    def test_duration_fades_finite_and_headroom(self):
        x = synthesize(self.config)
        self.assertEqual(x.size, 96000)
        self.assertTrue(np.isfinite(x).all())
        self.assertEqual(x[0], 0)
        self.assertEqual(x[-1], 0)
        self.assertLess(np.max(np.abs(x)), 1)

    def test_seed_and_linear_gain(self):
        x = synthesize(self.config)
        np.testing.assert_array_equal(x, synthesize(self.config))
        np.testing.assert_allclose(synthesize(replace(self.config, gain=0.075)), x / 2)
        self.assertFalse(np.array_equal(x, synthesize(replace(self.config, seed=7))))

    def test_harmonic_frequencies_weights_and_energy(self):
        x = synthesize(self.config)[12000:-12000]  # 1.5 s = 330 complete cycles
        f = np.fft.rfftfreq(x.size, 1 / self.config.sample_rate)
        amplitude = 2 * np.abs(np.fft.rfft(x)) / x.size
        frequencies, weights, _ = partials(self.config)
        bins = np.array([np.argmin(abs(f - hz)) for hz in frequencies])
        np.testing.assert_allclose(amplitude[bins], self.config.gain * weights, atol=1e-12)
        self.assertAlmostEqual(np.sqrt(np.mean(x**2)), self.config.gain / np.sqrt(2), places=12)
        amplitude[bins] = 0
        self.assertLess(np.max(amplitude), 1e-12)

    def test_invalid_parameters_rejected(self):
        for changes in ({"fundamental_hz": 4000}, {"gain": 0}, {"gain": float("nan")},
                        {"harmonics": 1.5}, {"harmonic_decay": -1}, {"seed": -1},
                        {"fade_s": 1}, {"fade_s": 0}, {"duration_s": -1},
                        {"spectral_profile": "unknown"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                synthesize(replace(self.config, **changes))

    def test_spectral_profiles(self):
        _, base_weights, base_phases = partials(self.config)
        for profile in ("power_law", "exponential", "odd_power_law"):
            config = replace(self.config, spectral_profile=profile)
            frequencies, weights, phases = partials(config)
            np.testing.assert_array_equal(phases, base_phases)
            self.assertAlmostEqual(float(np.sum(weights**2)), 1)
            x = synthesize(config)[12000:-12000]
            amplitude = 2 * np.abs(np.fft.rfft(x)) / x.size
            bins = np.rint(frequencies * x.size / config.sample_rate).astype(int)
            np.testing.assert_allclose(amplitude[bins], config.gain * weights, atol=1e-12)
            self.assertAlmostEqual(np.sqrt(np.mean(x**2)), config.gain / np.sqrt(2), places=12)
            if profile == "odd_power_law":
                np.testing.assert_array_equal(weights[1::2], 0)
            elif profile == "exponential":
                self.assertAlmostEqual(weights[1] / weights[0], np.exp(-config.harmonic_decay))
            else:
                np.testing.assert_array_equal(weights, base_weights)

    def test_excessive_peak_rejected_without_limiting(self):
        with self.assertRaisesRegex(ValueError, "clip"):
            synthesize(replace(self.config, harmonics=50, harmonic_decay=0.01, gain=0.99))

    def test_cli_wav_and_metadata_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            wav = Path(directory) / "test.wav"
            command = [sys.executable, "-m", "sonification_stimuli", "--duration", "2", "--output", str(wav)]
            subprocess.run(command, check=True, capture_output=True)
            digest = hashlib.sha256(wav.read_bytes()).hexdigest()
            info = sf.info(wav)
            self.assertEqual((info.frames, info.samplerate, info.channels, info.subtype),
                             (96000, 48000, 1, "PCM_24"))
            report = json.loads(wav.with_suffix(".json").read_text())
            self.assertEqual(report["sha256_wav"], digest)
            self.assertGreater(wav.with_suffix(".png").stat().st_size, 0)
            subprocess.run(command, check=True, capture_output=True)
            self.assertEqual(hashlib.sha256(wav.read_bytes()).hexdigest(), digest)


if __name__ == "__main__":
    unittest.main()
