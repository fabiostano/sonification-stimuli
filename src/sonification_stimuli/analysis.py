"""Digital descriptors, explicitly separate from calibrated psychoacoustics."""

import numpy as np
from scipy.signal import periodogram

from .synthesis import DroneConfig


def steady_segment(signal: np.ndarray, config: DroneConfig) -> np.ndarray:
    nf = round(config.fade_s * config.sample_rate)
    return signal[nf:-nf]


def spectrum(signal: np.ndarray, sample_rate: int) -> tuple[np.ndarray, np.ndarray]:
    """One-sided Hann-windowed PSD, amplitude units squared per Hz."""
    return periodogram(signal, fs=sample_rate, window="hann", detrend=False, scaling="density")


def analyze(signal: np.ndarray, config: DroneConfig) -> dict:
    steady = steady_segment(signal, config)
    frequencies, psd = spectrum(steady, config.sample_rate)
    peak = float(np.max(np.abs(signal)))
    rms = float(np.sqrt(np.mean(signal ** 2)))
    steady_rms = float(np.sqrt(np.mean(steady ** 2)))
    return {
        "samples": int(signal.size),
        "actual_duration_s": signal.size / config.sample_rate,
        "sample_peak_dbfs": float(20 * np.log10(peak)),
        "full_rms_dbfs": float(20 * np.log10(rms)),
        "steady_rms_dbfs": float(20 * np.log10(steady_rms)),
        "crest_factor_db": float(20 * np.log10(peak / rms)),
        "dc_offset": float(np.mean(signal)),
        "steady_power_centroid_hz": float(np.sum(frequencies * psd) / np.sum(psd)),
        "rms_convention": "20*log10(rms/1.0); full-scale sine = -3.0103 dBFS",
        "scope": "Digital descriptors only; no SPL, perceived loudness, sharpness or roughness estimate",
    }


def plot(signal: np.ndarray, config: DroneConfig, path, max_frequency_hz=None) -> None:
    # File rendering works without a display server.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), constrained_layout=True)
    t = np.arange(signal.size) / config.sample_rate
    # Per-bin extrema preserve waveform peaks in the full-duration overview.
    step = max(1, signal.size // 3000)
    starts = np.arange(0, signal.size, step)
    axes[0].fill_between(t[starts], np.minimum.reduceat(signal, starts),
                         np.maximum.reduceat(signal, starts), linewidth=0)
    axes[0].set(xlabel="Time (s)", ylabel="Amplitude (FS)", title="Full stimulus (binned min/max envelope)")
    middle = signal.size // 2
    end = min(signal.size, middle + round(0.05 * config.sample_rate))
    axes[1].plot(t[middle:end] - t[middle], signal[middle:end], linewidth=0.8)
    axes[1].set(xlabel="Time within excerpt (s)", ylabel="Amplitude (FS)", title="50 ms steady-state waveform")
    f, psd = spectrum(steady_segment(signal, config), config.sample_rate)
    axes[2].plot(f, 10 * np.log10(np.maximum(psd, 1e-16)), linewidth=0.8)
    axes[2].set(xlabel="Frequency (Hz)", ylabel="PSD (dB re 1 FS²/Hz)",
                title="Steady region: Hann-windowed power spectral density",
                xlim=(0, min(config.sample_rate / 2, max_frequency_hz if max_frequency_hz is not None
                             else config.fundamental_hz * (config.harmonics + 2))))
    for axis in axes:
        axis.grid(alpha=0.25)
    fig.savefig(path, dpi=160)
    plt.close(fig)
