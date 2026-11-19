# Sonification stimuli

A minimal, reproducible harmonic-drone prototype for a magnitude-estimation study. This first version generates **one provisional reference**, not a validated perceptual midpoint or the eventual 21-stimulus set. Pleasantness and suitability for sustained listening require listening evaluation.

## Setup and first listen

Python 3.11 or newer is required (development environment: Python 3.13). From this directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
drone --config configs/reference.toml
```

The supplied workspace already has its virtual environment installed. To reproduce the dependency versions used here in a new environment, replace the installation command with:

```sh
python -m pip install -r requirements-lock.txt
python -m pip install --no-deps --no-build-isolation -e .
```

Listen on macOS and open the plot:

```sh
afplay outputs/reference.wav
open outputs/reference.png
```

Alternatively open the WAV in your usual audio player. Start with playback volume low and adjust to a comfortable level. Digital gain does not specify acoustic sound pressure at your ears. Playback is intentionally manual; generation does not start audio automatically.

## Iterate

Edit `configs/reference.toml`, rerun the command, and listen again. CLI values override the TOML file:

```sh
drone --config configs/reference.toml --f0 180 --decay 1.8 --gain 0.12 --output outputs/trial-01.wav
```

This is a control example, not a proposed experimental level. Use a new output name to retain each candidate; rerunning the same name replaces its WAV, JSON, and PNG. Without `--config`, the same initial defaults are used. Run `drone --help` for controls. Duration can also be overridden with `--duration 12`. Keep the phase seed, harmonic count, fades, playback chain, and listening volume fixed during initial comparisons. Record subjective notes separately; no pleasantness or mental-state mapping is assumed.

Each run produces:

- A mono, 48 kHz, 24-bit PCM WAV (sample rate is configurable).
- A JSON sidecar containing all parameters, exact harmonic phases/weights/frequencies, package and libsndfile versions, WAV SHA-256, and digital measurements.
- A PNG containing a full-duration waveform envelope, a 50 ms waveform excerpt, and the steady-region spectrum.

## Synthesis model and every parameter

For harmonic index `k = 1 … K`, the default relative amplitude is `a_k = k^(-p)`. Alternative spectral profiles are described in [the audition guide](docs/auditions.md). We set `w_k = a_k / sqrt(sum(a_k²))` and synthesize:

```text
x[n] = gain × envelope[n] × Σ w_k sin(2π k f0 n / sample_rate + phase_k)
```

| Parameter | Initial value | Meaning and consequences |
| --- | --- | --- |
| `fundamental_hz` (`--f0`) | 220 Hz | Harmonics lie at integer multiples of this frequency. Changing it shifts both pitch and the absolute spectral distribution. |
| `harmonics` | 8, including fundamental | Fixed number of partials; highest initial partial is 1760 Hz. Harmonics at or above Nyquist are rejected rather than silently removed, which would change timbre. |
| `harmonic_decay` (`--decay`) | 1.5 | Positive amplitude exponent `p`; larger values suppress upper harmonics. This is a synthesis control, not a validated brightness scale. |
| `gain` (`--gain`) | 0.15 | Linear multiplier after harmonic-weight normalization, before export. Gain is not a target peak, RMS in dB, or loudness value. |
| `duration_s` (`--duration`) | 12 s | Total duration including fades; sample count is `round(duration_s × sample_rate)`. |
| `sample_rate` | 48000 Hz | Sampling frequency; synthesis uses float64 calculations. |
| `fade_s` | 0.75 s each end | Raised-cosine amplitude ramps from exactly zero to one and back. Length is rounded to samples; ramps must leave a steady region. |
| `seed` | 20261016 | Nonnegative PCG64 seed for uniform initial phases in `[0, 2π)`. Phases stay constant over time. There is no noise or time-varying random process. |
| `spectral_profile` (`--profile`) | `power_law` | Relative amplitude rule: `power_law`, `exponential`, or `odd_power_law`. These are alternative timbral candidates, not experimental levels. |

No chords, melody, detuning, filtering, reverb, compression, noise, or deliberate amplitude modulation are added. Static random phases avoid forcing all partials to start with the same phase; they still determine waveform shape and crest factor. Holding the seed and harmonic count fixed holds those phases fixed between candidates. The code never changes the global random state. The exact realized phases are saved because a seed alone is not a complete cross-version reproducibility specification ([NumPy generator documentation](https://numpy.org/doc/stable/reference/random/generator.html)).

Raised-cosine fades reduce onset/offset discontinuities and have zero slope at their ends. They necessarily introduce envelope variation and spectral spreading near the boundaries. Analyses of the sustained portion exclude both fades. This is a finite-duration signal, so a spectrum will still show windowing effects.

## Acoustic confounds and loudness

Unit-L2 harmonic weighting holds the theoretical mean-square value of the unwindowed periodic signal at `gain²/2`. At the default gain its ideal steady RMS is about −19.49 dBFS. Finite segments that do not span complete periods can depart slightly from that value; fades lower the full-file RMS. Changing decay redistributes energy across partials, including the fundamental. This energy convention is explicit rather than an implicit peak normalization after each render.

**Equal energy does not imply equal perceived loudness.** This prototype does not perform perceptual loudness matching or calibrated psychoacoustic analysis. Frequency, spectral distribution, modulation, listening level, and the playback system can all matter. The JSON uses digital full-scale units, not Pa or dB SPL. An SPL-calibrated playback chain and an appropriate loudness model, followed by listening validation/matching, are later steps before experimental use. MoSQITo's [stationary Zwicker loudness API](https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.loudness.loudness_zwst.loudness_zwst.html) expects calibrated pressure in Pa; uncalibrated WAV amplitudes must not simply be treated as Pa. Model choice must be revisited for modulated stimuli.

Pitch and brightness cannot be assumed independent here: fixed relative harmonic weights move to different absolute frequencies when f0 changes. Similarly, later fast/slow AM will add sidebands and can change both energy and perception; adding noise will redistribute energy and affect loudness and brightness. The present reference has no deliberate roughness, noisiness, or pulsation control, and should not yet be called the middle level of those dimensions. Establish their baselines and manipulation checks after listening refinement.

Sample peaks at or above full scale raise an error before export. There is no clipping, limiting, automatic gain correction, or peak normalization. The reported sample peak is not an oversampled true-peak measurement. Export uses 24-bit PCM via [SoundFile](https://python-soundfile.readthedocs.io/), without added dither; quantization is very small but the exported signal is not mathematically noise-free. All reported measurements and plots use the decoded WAV, so export effects are included.

## Measurements and plots

The JSON reports full and steady RMS, sample peak, full-file crest factor, mean/DC offset, duration, and a **power-weighted** spectral centroid. RMS dBFS is `20 log10(rms / 1)`; a full-scale sine has RMS −3.0103 dBFS in this convention. The centroid is an acoustic descriptor, not perceptual brightness, sharpness, or a loudness measurement.

The spectrum is a one-sided Hann-windowed power spectral density from the steady portion, computed with [SciPy's periodogram](https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.periodogram.html), with no mean removal. Its axis is dB relative to 1 FS²/Hz, not harmonic amplitude or SPL. The displayed frequency span follows the requested partials. Hann windowing spreads spectral lines; it does not add noise to the WAV. The full waveform plot uses bin minima/maxima to preserve peaks while keeping the figure manageable.

## Project layout and verification

```text
configs/reference.toml           provisional listening configuration
src/sonification_stimuli/        synthesis, analysis, and CLI
tests/test_synthesis.py          signal invariants and export integration
outputs/                        generated WAV, metadata, and plots (Git-ignored)
pyproject.toml                  package and direct dependency constraints
requirements-lock.txt           resolved environment versions
```

```sh
source .venv/bin/activate
python -m unittest discover -s tests -v
python -m pip check
```

Checks cover duration, finite samples, silent endpoints, headroom, gain linearity, seeded reproducibility, harmonic frequencies/amplitudes, theoretical energy, invalid settings, clipping rejection, PCM format, sidecar checksum, plot creation, and repeated byte-identical exports in the tested environment. They cannot establish pleasantness or perceptual equality.

Git is initialized on `main`; source/configuration should be versioned, while the virtual environment and generated outputs are ignored. Line endings and binary audio/image treatment are specified in `.gitattributes`. No remote or user identity is configured. For publication, archive selected WAVs and their sidecars, configuration, source revision, locked environment, and playback/calibration procedure. Exact bytes across different platforms/library versions are not guaranteed; use the saved checksum to verify archived files.

## Alternative timbre auditions

Three additional 12-second candidates are configured in `configs/auditions/` and rendered in `outputs/auditions/`. See [listening instructions and design tradeoffs](docs/auditions.md). The original `outputs/reference.wav` remains the first candidate.

## First complete exploratory set

The rounded profile is now the provisional carrier. A 21-stimulus listening set covers pitch, brightness, roughness, noisiness, and pulsation, with one shared reference and four variants per dimension. Five ordered listening tracks are available in `outputs/exploratory_v1/previews/`. See [the set guide](docs/exploratory-set.md) for the provisional ranges, generation command, processing order, and confounds. The shared reference adds some noise and modulation so values can lie below and above it. Steady RMS is matched; perceived loudness is **not** yet matched. Earlier audition files are preserved.

## Web demonstrator

The [Auditory Stimulus Explorer](sites/stimulus-explorer/README.md) now supports live synthesis of all 15,625 combinations of six five-point controls for five characteristics, with separate browser workers for synthesis and MoSQiTo psychoacoustic estimates. Three panels show controls, simultaneous signal views, and model/parameter diagnostics. Pulse frequency and pulse depth are independently adjustable in both tabs. The original 21 Python stimuli and their experimental specification remain in the research project. Loudness, roughness and sharpness estimates use an explicit adjustable reference-SPL assumption, not a hardware calibration. Waveforms, spectra, digital diagnostics, and downloadable reports update with the selected sound. See its README for local serving instructions and model-validation details.

A second Source audio tab accepts a local WAV/MP3 excerpt with a neutral middle reference and exploratory relative effects. Its content-dependent operations are documented separately from the drone's experimental controls.

## Endpoint CSVs saved in this project

Browser CSV downloads remain available. Local generation and unchanged browser-CSV imports now also save measurements to `outputs/endpoint-comparisons/`, with one CSV/provenance JSON per base and an `all-endpoint-comparisons.csv` combining saved records.

```sh
.venv/bin/python -m sonification_stimuli.endpoints --drone
.venv/bin/python -m sonification_stimuli.endpoints --source "stimuli/base stimuli/stim_amb_1.mp3"
.venv/bin/python -m sonification_stimuli.endpoints --import-csv "$HOME/Downloads/base-endpoint-comparison.csv"
```

The local exporter reuses the app's renderer, endpoint design, CSV formatting and Python models. Native and browser results retain separate backend identities and decoding provenance. Importing a browser CSV preserves its original bytes and scores. See [setup, workflow and interpretation](docs/endpoint-exports.md).

For low-barrier analysis, open `outputs/endpoint-comparisons/analysis.html` directly in a browser. It includes an interactive change matrix, raw-value comparisons across bases, a Matplotlib overview PNG and a tidy summary CSV. Local exports/imports refresh it automatically. Regenerate it independently with `.venv/bin/python -m sonification_stimuli.endpoint_report`. See [the analysis guide](docs/endpoint-analysis.md).

The report also compares bases using a proposed selectivity score: normalized target benefit minus a weighted RMS penalty for unintended changes, including loudness. An adjustable penalty slider, explicit common/full comparison scope, per-control breakdown and PNG/CSV/JSON exports support inspection. See [the formula and assumptions](docs/base-selectivity.md).
