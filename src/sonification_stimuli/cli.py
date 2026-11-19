"""Generate one WAV plus its configuration, measurements and plot."""

import argparse
from dataclasses import asdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import tomllib

import soundfile as sf

from .analysis import analyze, plot
from .synthesis import DroneConfig, partials, synthesize


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="TOML file containing DroneConfig fields")
    parser.add_argument("--f0", type=float, help="Fundamental frequency (Hz)")
    parser.add_argument("--decay", type=float, help="Positive spectral decay parameter; interpretation depends on profile")
    parser.add_argument("--profile", choices=("power_law", "exponential", "odd_power_law"), help="Harmonic amplitude profile")
    parser.add_argument("--gain", type=float, help="Linear gain after unit-energy harmonic weighting")
    parser.add_argument("--duration", type=float, help="Duration including fades (seconds)")
    parser.add_argument("--output", type=Path, default=Path("outputs/reference.wav"))
    args = parser.parse_args()
    if args.output.suffix.lower() != ".wav":
        parser.error("--output must have a .wav extension")
    try:
        values = tomllib.loads(args.config.read_text()) if args.config else {}
        for argument, field in (("f0", "fundamental_hz"), ("decay", "harmonic_decay"),
                                ("gain", "gain"), ("duration", "duration_s"),
                                ("profile", "spectral_profile")):
            if getattr(args, argument) is not None:
                values[field] = getattr(args, argument)
        config = DroneConfig(**values)
        signal = synthesize(config)
    except (TypeError, ValueError, OSError) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.output, signal, config.sample_rate, format="WAV", subtype="PCM_24")
    # Analyze decoded exported samples, including PCM quantization.
    exported, _ = sf.read(args.output, dtype="float64")
    frequencies, weights, phases = partials(config)
    report = {
        "config": asdict(config),
        "synthesis": "sum(gain * unit-L2 spectral weights * sin(2*pi*k*f0*t + phase)); raised-cosine fades",
        "spectral_weight_formula": {
            "power_law": "k^(-decay)",
            "exponential": "exp(-decay*(k-1))",
            "odd_power_law": "k^(-decay) for odd k; zero for even k",
        }[config.spectral_profile],
        "partials_hz": frequencies.tolist(),
        "partial_weights": weights.tolist(),
        "partial_phases_rad": phases.tolist(),
        "random_generator": "NumPy Generator(PCG64(seed)); phases fixed over time",
        "export": {"format": "WAV", "subtype": "PCM_24", "channels": 1, "dither": False},
        "sha256_wav": hashlib.sha256(args.output.read_bytes()).hexdigest(),
        "versions": {name: version(name) for name in ("sonification-stimuli", "numpy", "scipy", "soundfile", "matplotlib")},
        "python": platform.python_version(),
        "libsndfile": sf.__libsndfile_version__,
        "analysis": analyze(exported, config),
    }
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    plot(exported, config, args.output.with_suffix(".png"))
    print(f"Wrote {args.output}, {args.output.with_suffix('.json')}, {args.output.with_suffix('.png')}")
    print(json.dumps(report["analysis"], indent=2))
