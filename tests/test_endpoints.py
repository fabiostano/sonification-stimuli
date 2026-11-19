"""Project CSV archive integrity, endpoint validation and source decode contracts."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile as sf

from sonification_stimuli.endpoints import (
    archive_browser_csv, combine, decode_source, read_table, CONDITIONS, DIMENSIONS,
)


def browser_fixture(path, rows=None):
    if rows is None:
        rows = []
        for target, level in sorted(CONDITIONS):
            row = {"batch_id": "browser-base", "created_at_utc": "2026-11-03T12:00:00Z",
                   "target_characteristic": target, "condition_level": level,
                   "wav_sha256": "a" * 64, "model_status": "ok", "assumed_reference_spl_db": 60,
                   "loudness_sone": 2, "roughness_asper": .1, "sharpness_acum": 1,
                   "source_id": "original-source", "source_file": "base, one.wav",
                   "model_metadata_json": json.dumps({"runtime": {"engine": "Pyodide"}})}
            row.update({f"setting_{dimension}_level": level if dimension == target else 3 for dimension in DIMENSIONS})
            rows.append(row)
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return rows


class EndpointArchiveTests(unittest.TestCase):
    def test_exact_import_dedup_and_backend_in_combined_csv(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "download.csv"
            browser_fixture(source)
            original = source.read_bytes()
            first = archive_browser_csv(source, root / "project-outputs")
            self.assertEqual(first.read_bytes(), original)
            self.assertEqual(archive_browser_csv(source, root / "project-outputs"), first)
            combined, count = combine(root / "project-outputs")
            self.assertEqual(count, 13)
            rows = read_table(combined)
            self.assertTrue(all(row["input_mode"] == "source" for row in rows))
            self.assertTrue(all(row["analysis_backend"] == "browser-pyodide" for row in rows))
            manifest = json.loads(first.with_suffix(".json").read_text())
            self.assertEqual(manifest["sha256_csv"], hashlib.sha256(original).hexdigest())

            # An app-wide CSV can add empty columns; importing it must not duplicate rows.
            expanded = [{**row, "additional_column": ""} for row in read_table(source)]
            browser_fixture(root / "expanded.csv", expanded)
            archive_browser_csv(root / "expanded.csv", root / "project-outputs")
            self.assertEqual(combine(root / "project-outputs")[1], 13)

    def test_incomplete_and_confounded_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.csv"
            rows = browser_fixture(path)
            browser_fixture(path, rows[:-1])
            with self.assertRaisesRegex(ValueError, "twelve endpoints"):
                read_table(path)
            rows[0]["setting_brightness_level"] = 1
            rows[0]["setting_pitch_level"] = 5
            browser_fixture(path, rows)
            with self.assertRaisesRegex(ValueError, "one-control"):
                read_table(path)

    def test_conflicts_preserve_the_previous_combined_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = browser_fixture(root / "original.csv")
            archive_browser_csv(root / "original.csv", root / "out")
            combined, _ = combine(root / "out")
            previous = combined.read_bytes()
            rows[0]["loudness_sone"] = 99
            browser_fixture(root / "conflict.csv", rows)
            archive_browser_csv(root / "conflict.csv", root / "out")
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                combine(root / "out")
            self.assertEqual(previous, combined.read_bytes())

    def test_source_decode_downmix_bounds_and_resampling(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fs = 48000
            t = np.arange(5 * fs) / fs
            mono = .1 * np.sin(2 * np.pi * 330 * t)
            path = root / "stereo.wav"
            sf.write(path, np.column_stack([mono, mono * .5]), fs, subtype="PCM_24")
            samples, metadata, decode = decode_source(path, .5, 4)
            decoded, _ = sf.read(path, always_2d=True)
            np.testing.assert_array_equal(samples, decoded.mean(axis=1)[24000:216000])
            self.assertEqual(metadata["excerpt_start_s"], .5)
            self.assertEqual(metadata["decoded_channels"], 2)
            self.assertEqual(decode["resampling"], "none")
            with self.assertRaises(ValueError):
                decode_source(path, 2, 4)
            with self.assertRaises(ValueError):
                decode_source(path, float("nan"), 4)
            sf.write(root / "44100.wav", np.zeros(5 * 44100), 44100)
            samples, metadata, decode = decode_source(root / "44100.wav", 0, 4)
            self.assertEqual(len(samples), 4 * 48000)
            self.assertEqual(decode["original_sample_rate_hz"], 44100)
            self.assertIn("polyphase", decode["resampling"])


if __name__ == "__main__":
    unittest.main()
