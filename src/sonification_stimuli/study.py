"""Exploratory one-factor-at-a-time sets; no perceptual matching implied.

Run: python -m sonification_stimuli.study --config configs/exploratory_set.json
"""

import argparse
import csv
from dataclasses import asdict, dataclass, field, replace
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil

import numpy as np
import soundfile as sf

from .analysis import analyze, plot
from .synthesis import DroneConfig, partials


LABELS = ("very_low", "low", "high", "very_high")
DIMENSIONS = {
    "pitch": ("fundamental_hz", "Hz", False),
    "brightness": ("harmonic_decay", "exponential decay coefficient", True),
    "roughness": ("roughness_depth", "fast AM depth (0..1)", False),
    "noisiness": ("hnr_db", "source component HNR (dB)", True),
    "pulsation": ("pulsation_hz", "Hz", False),
}


@dataclass(frozen=True)
class StimulusConfig:
    carrier: DroneConfig = field(default_factory=lambda: DroneConfig(
        spectral_profile="exponential", harmonic_decay=1.2))
    roughness_depth: float = 0.2
    fast_am_hz: float = 70.0
    hnr_db: float = 24.0
    pulsation_hz: float = 2.0
    slow_am_depth: float = 0.25
    noise_low_hz: float = 100.0
    noise_high_hz: float = 4000.0
    noise_seed: int = 20261017

    def validate(self):
        self.carrier.validate()
        for name, value in asdict(self).items():
            if name != "carrier" and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not np.isfinite(value)):
                raise ValueError(f"{name} must be a finite number")
        if not isinstance(self.noise_seed, int) or self.noise_seed < 0:
            raise ValueError("noise_seed must be a nonnegative integer")
        if not 0 <= self.roughness_depth <= 1 or not 0 < self.slow_am_depth <= 1:
            raise ValueError("Require fast AM depth in [0,1] and slow AM depth in (0,1]")
        if not 0 < self.pulsation_hz < 20 or not 20 <= self.fast_am_hz <= 150:
            raise ValueError("Require slow AM rate in (0,20) and fast AM rate in [20,150]")
        if not 0 <= self.hnr_db <= 120:
            raise ValueError("Require source HNR between 0 and 120 dB")
        if not 0 < self.noise_low_hz < self.noise_high_hz < self.carrier.sample_rate / 2:
            raise ValueError("Noise band must lie strictly within (0, Nyquist)")
        highest = self.carrier.harmonics * self.carrier.fundamental_hz
        if highest + self.fast_am_hz + self.pulsation_hz >= self.carrier.sample_rate / 2:
            raise ValueError("AM sidebands would reach Nyquist")


def rms(x):
    return float(np.sqrt(np.mean(x * x)))


def render(config: StimulusConfig) -> tuple[np.ndarray, dict]:
    """Return faded mono samples and source-component diagnostics.

    Component HNR includes both AM stages as part of the tonal source; it is
    not an acoustic HNR estimator applied to the final waveform.
    """
    config.validate()
    c = config.carrier
    n = round(c.duration_s * c.sample_rate)
    nf = round(c.fade_s * c.sample_rate)
    steady = slice(nf, -nf)
    t = np.arange(n) / c.sample_rate
    frequencies, weights, phases = partials(c)
    harmonic = np.zeros(n)
    for frequency, weight, phase in zip(frequencies, weights, phases):
        harmonic += weight * np.sin(2 * np.pi * frequency * t + phase)
    fast = 1 + config.roughness_depth * np.sin(2 * np.pi * config.fast_am_hz * t)
    slow = 1 + config.slow_am_depth * np.sin(2 * np.pi * config.pulsation_hz * t)
    harmonic *= fast * slow
    harmonic /= rms(harmonic[steady])

    # Hard FFT band selection is explicit, offline, and reproducible. Fades
    # suppress boundary discontinuities in the finite noise realization.
    rng = np.random.Generator(np.random.PCG64(config.noise_seed))
    noise_fft = np.fft.rfft(rng.standard_normal(n))
    fft_hz = np.fft.rfftfreq(n, 1 / c.sample_rate)
    noise_fft[(fft_hz < config.noise_low_hz) | (fft_hz > config.noise_high_hz)] = 0
    noise = np.fft.irfft(noise_fft, n=n)
    noise /= rms(noise[steady])
    noise *= 10 ** (-config.hnr_db / 20)

    mixture = harmonic + noise  # Noise is not intentionally AM-modulated.
    target_rms = c.gain / np.sqrt(2)
    mix_gain = target_rms / rms(mixture[steady])
    mixture *= mix_gain
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, nf))
    mixture[:nf] *= ramp
    mixture[-nf:] *= ramp[::-1]
    if not np.isfinite(mixture).all() or np.max(np.abs(mixture)) >= 1:
        raise ValueError("Nonfinite or clipping waveform: reduce carrier.gain")
    diagnostics = {
        "target_steady_rms_dbfs": float(20 * np.log10(target_rms)),
        "source_hnr_db": float(20 * np.log10(rms(harmonic[steady]) / rms(noise[steady]))),
        "source_correlation": float(np.corrcoef(harmonic[steady], noise[steady])[0, 1]),
        "final_linear_mix_gain": mix_gain,
        "carrier_frequencies_hz": frequencies.tolist(),
        "carrier_unit_l2_weights": weights.tolist(),
        "carrier_phases_rad": phases.tolist(),
        "fast_envelope_min_max": [float(fast.min()), float(fast.max())],
        "slow_envelope_min_max": [float(slow.min()), float(slow.max())],
        "hnr_definition": "steady RMS power ratio of modulated tonal source to additive unmodulated noise; not estimated perceptual harmonicity",
    }
    return mixture, diagnostics


def conditions(spec: dict) -> list[tuple[str, str, str, StimulusConfig]]:
    carrier = DroneConfig(**spec["carrier"])
    reference = StimulusConfig(carrier=carrier, **spec["reference"])
    reference.validate()
    if carrier.spectral_profile != "exponential":
        raise ValueError("This set's brightness parameter requires the exponential profile")
    if set(spec["levels"]) != set(DIMENSIONS):
        raise ValueError("Exactly five dimensions are required")
    result = [("reference", "shared", "reference", reference)]
    for dimension, (parameter, _, reverse) in DIMENSIONS.items():
        values = spec["levels"][dimension]
        if len(values) != 4:
            raise ValueError(f"{dimension} requires four non-reference levels")
        middle = getattr(carrier if parameter in ("fundamental_hz", "harmonic_decay") else reference, parameter)
        ordered = [values[0], values[1], middle, values[2], values[3]]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and np.isfinite(v) for v in ordered):
            raise ValueError(f"Nonfinite/non-numeric levels in {dimension}")
        differences = np.diff(ordered)
        if not np.all(differences < 0 if reverse else differences > 0):
            raise ValueError(f"{dimension} levels must strictly bracket the reference in perceptual direction")
        for label, value in zip(LABELS, values):
            if parameter in ("fundamental_hz", "harmonic_decay"):
                config = replace(reference, carrier=replace(carrier, **{parameter: value}))
            else:
                config = replace(reference, **{parameter: value})
            config.validate()
            result.append((f"{dimension}_{label}", dimension, label, config))
    return result


def generate(spec: dict, output: Path, make_plots=True):
    entries = conditions(spec)  # Validate the entire specification before writing.
    output.mkdir(parents=True, exist_ok=True)
    # A new directory avoids mixing stale stimuli with the requested set.
    if any(output.iterdir()):
        raise ValueError("Output directory must be empty; choose a new name to preserve previous sets")
    (output / "specification.json").write_text(json.dumps(spec, indent=2) + "\n")
    shutil.copyfile(__file__, output / "generator_snapshot.py")
    versions = {name: version(name) for name in ("sonification-stimuli", "numpy", "scipy", "soundfile", "matplotlib")}
    rows = []
    for name, dimension, level, config in entries:
        samples, sources = render(config)
        wav = output / f"{name}.wav"
        sf.write(wav, samples, config.carrier.sample_rate, subtype="PCM_24")
        decoded, _ = sf.read(wav)
        measurements = analyze(decoded, config.carrier)
        report = {
            "id": name, "dimension": dimension, "level": level,
            "status": "exploratory; not loudness matched or perceptually validated",
            "config": asdict(config), "source_diagnostics": sources,
            "analysis": measurements, "sha256_wav": hashlib.sha256(wav.read_bytes()).hexdigest(),
            "versions": versions, "python": platform.python_version(),
            "libsndfile": sf.__libsndfile_version__,
            "export": {"format": "WAV", "subtype": "PCM_24", "channels": 1, "dither": False},
        }
        wav.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
        if make_plots:
            plot(decoded, config.carrier, wav.with_suffix(".png"), max_frequency_hz=config.noise_high_hz + config.fast_am_hz)
        parameter, unit, _ = DIMENSIONS.get(dimension, ("shared", "all reference parameters", False))
        value = "reference" if dimension == "shared" else getattr(
            config.carrier if parameter in ("fundamental_hz", "harmonic_decay") else config, parameter)
        rows.append({"id": name, "dimension": dimension, "level": level,
                     "parameter": parameter, "value": value, "unit": unit,
                     "wav": wav.name, "sha256_wav": report["sha256_wav"], **measurements})
        print(f"Rendered {name}", flush=True)
    with (output / "manifest.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    # Convenience playlists contain the same decoded files, never new renders.
    previews = output / "previews"
    previews.mkdir()
    timing = {}
    sample_rate = entries[0][3].carrier.sample_rate
    for dimension in DIMENSIONS:
        ids = [f"{dimension}_{LABELS[0]}", f"{dimension}_{LABELS[1]}", "reference",
               f"{dimension}_{LABELS[2]}", f"{dimension}_{LABELS[3]}"]
        chunks, segments, cursor = [], [], 0
        for i, name in enumerate(ids):
            samples, _ = sf.read(output / f"{name}.wav")
            chunks.append(samples)
            segments.append({"id": name, "start_s": cursor / sample_rate,
                             "end_s": (cursor + samples.size) / sample_rate})
            cursor += samples.size
            if i < len(ids) - 1:
                chunks.append(np.zeros(sample_rate))
                cursor += sample_rate
        sf.write(previews / f"{dimension}.wav", np.concatenate(chunks), sample_rate, subtype="PCM_24")
        timing[dimension] = segments
    (previews / "timing.json").write_text(json.dumps(timing, indent=2) + "\n")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/exploratory_set.json"))
    parser.add_argument("--output", type=Path, default=Path("outputs/exploratory_v1"))
    args = parser.parse_args()
    try:
        generate(json.loads(args.config.read_text()), args.output)
    except (ValueError, TypeError, KeyError, OSError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
