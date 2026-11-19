"""Additive synthesis with explicit energy scaling and static phases."""

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class DroneConfig:
    fundamental_hz: float = 220.0
    harmonics: int = 8
    harmonic_decay: float = 1.5
    gain: float = 0.15
    duration_s: float = 12.0
    sample_rate: int = 48000
    fade_s: float = 0.75
    seed: int = 20261016
    spectral_profile: str = "power_law"

    def validate(self) -> None:
        if self.spectral_profile not in ("power_law", "exponential", "odd_power_law"):
            raise ValueError("spectral_profile must be power_law, exponential, or odd_power_law")
        for name in ("fundamental_hz", "harmonic_decay", "gain", "duration_s", "fade_s"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        for name in ("harmonics", "sample_rate", "seed"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer")
        if self.harmonics < 1 or self.sample_rate < 1 or self.seed < 0:
            raise ValueError("harmonics/sample_rate must be positive; seed must be nonnegative")
        if self.fundamental_hz <= 0 or self.harmonic_decay <= 0:
            raise ValueError("fundamental_hz and harmonic_decay must be positive")
        if self.harmonics * self.fundamental_hz >= self.sample_rate / 2:
            raise ValueError("All requested harmonics must lie strictly below Nyquist")
        if not 0 < self.gain < 1:
            raise ValueError("gain must lie strictly between 0 and 1")
        n = round(self.duration_s * self.sample_rate)
        nf = round(self.fade_s * self.sample_rate)
        if self.duration_s <= 0 or self.fade_s <= 0 or nf < 2 or 2 * nf >= n:
            raise ValueError("Require positive duration, fades >= 2 samples, and a steady region")


def partials(config: DroneConfig) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return frequencies, unit-L2 weights, and reproducible phases (radians)."""
    config.validate()
    k = np.arange(1, config.harmonics + 1, dtype=float)
    weights = k ** (-config.harmonic_decay)
    if config.spectral_profile == "exponential":
        weights = np.exp(-config.harmonic_decay * (k - 1))
    elif config.spectral_profile == "odd_power_law":
        weights[1::2] = 0
    weights /= np.linalg.norm(weights)
    rng = np.random.Generator(np.random.PCG64(config.seed))
    phases = rng.uniform(0, 2 * np.pi, config.harmonics)
    return k * config.fundamental_hz, weights, phases


def synthesize(config: DroneConfig) -> np.ndarray:
    """Return float64 mono samples; never limit, clip, or peak-normalize."""
    frequencies, weights, phases = partials(config)
    t = np.arange(round(config.duration_s * config.sample_rate)) / config.sample_rate
    signal = np.zeros(t.size, dtype=np.float64)
    for frequency, weight, phase in zip(frequencies, weights, phases):
        signal += weight * np.sin(2 * np.pi * frequency * t + phase)
    nf = round(config.fade_s * config.sample_rate)
    ramp = 0.5 - 0.5 * np.cos(np.linspace(0, np.pi, nf))
    signal[:nf] *= ramp
    signal[-nf:] *= ramp[::-1]
    signal *= config.gain
    if np.max(np.abs(signal)) >= 1:
        raise ValueError("Signal would clip: reduce gain; no automatic rescaling applied")
    return signal
