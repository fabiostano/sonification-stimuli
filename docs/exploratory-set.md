# Exploratory five-dimension stimulus set, v1

This is the first complete **listening prototype**, built from the preferred rounded harmonic profile. It contains 21 unique 12-second stimuli: four alternatives for each of five dimensions and one shared reference. Labels such as Very High denote the intended synthesis direction; they are not validated perceptual magnitudes, equal perceptual steps, or final experimental ranges. No association with a mental state is assumed.

## Listen first

The shared reference is `outputs/exploratory_v1/reference.wav`. It differs from the previously preferred `outputs/auditions/rounded.wav`: it includes moderate fast AM, slow AM, and noise so the same reference can lie between lower and higher values of every control. A zero-noise, unmodulated reference cannot have two levels below it on noise or modulation depth. The earlier rounded WAV is preserved.

Five convenience tracks are in `outputs/exploratory_v1/previews/`:

```sh
afplay outputs/exploratory_v1/previews/pitch.wav
afplay outputs/exploratory_v1/previews/brightness.wav
afplay outputs/exploratory_v1/previews/roughness.wav
afplay outputs/exploratory_v1/previews/noisiness.wav
afplay outputs/exploratory_v1/previews/pulsation.wav
```

Each track is 64 seconds: **Very Low → Low → Reference → High → Very High**, with each stimulus lasting 12 seconds and separated by one second of silence. Segment starts are 0, 13, 26, 39, and 52 seconds. The middle segment is copied from the same reference WAV in every track. Preview tracks are concatenations for auditioning, not additional experimental conditions. They contain no spoken labels. Listen to individual files for replay or a different order; the ordered previews are not a study presentation protocol.

Note whether successive levels are distinguishable, whether ordering feels right, which sounds become unpleasant, and whether loudness differences dominate. Keep the initial playback setting fixed and record any adjustments. The high pitch extends above your preferred register as an exploratory endpoint; its comfort may limit the final range.

## Provisional parameters

| Dimension / control | Very Low | Low | Shared reference | High | Very High |
| --- | --- | --- | --- | --- | --- |
| Pitch: f0, Hz | 165 | 196 | 220 | 247 | 294 |
| Brightness: exponential decay | 2.4 | 1.7 | 1.2 | 0.8 | 0.45 |
| Roughness: 70 Hz AM depth | 0 | 0.10 | 0.20 | 0.40 | 0.70 |
| Noisiness: source HNR, dB | 36 | 30 | 24 | 18 | 12 |
| Pulsation: slow AM rate, Hz | 0.5 | 1 | 2 | 3 | 5 |

Each non-reference stimulus changes exactly one configured control. Lower spectral decay means more high-harmonic energy; lower HNR means more noise. Those two numeric controls therefore decrease as the intended dimension increases. Slow AM depth stays at 0.25; fast AM rate stays at 70 Hz. Neither AM rate is randomized. The reference remains a provisional point, not a perceptual midpoint.

Carrier defaults: eight harmonic indices, exponential amplitudes `exp(-decay*(k-1))` with unit-L2 normalization, f0 220 Hz, phase seed 20261016, 48 kHz mono, 12 seconds including two 0.75-second raised-cosine fades. Other values remain as specified in the JSON configuration. Noise has a separate seed, 20261017.

## Exact processing order and scaling

1. Synthesize the harmonic carrier in float64, using fixed seeded initial phases for each harmonic index.
2. Multiply the carrier by `(1 + fast_depth*sin(2π*70*t))` and `(1 + 0.25*sin(2π*slow_rate*t))`. Both modulation phases are zero at the first sample. Depth 0 means no fast modulation; depth 1 reaches a zero envelope minimum. The product produces interactions and additional sidebands.
3. Normalize the resulting tonal component to unit RMS over the steady region excluding both fades.
4. Generate seeded Gaussian noise, retain FFT bins from 100 to 4000 Hz inclusive, and inverse-transform it. This is nominally flat-power-density band-limited noise, not pink noise. Normalize its steady RMS and scale it to `10^(-HNR/20)` relative to the tonal component. The same noise realization is reused in all conditions at a fixed duration/sample rate. Changing duration changes the realization and FFT grid even with the same seed.
5. Add the noise to the modulated tonal component. The noise is not deliberately amplitude-modulated. This keeps the noise source fixed when AM controls change, but it dilutes the observable envelope, especially at higher noise levels.
6. Apply one scalar to match measured mixture steady RMS to `carrier.gain/sqrt(2)` (−19.4885 dBFS at gain 0.15), then apply the common fades. Component normalization and mixture RMS scaling are explicit parts of this set, beyond the simple additive prototype. Finite source correlation is recorded, not assumed zero.
7. Reject clipping rather than limiting or peak-normalizing. Export PCM-24 without added dither; analyze the decoded WAV. Quantization and fades introduce tiny departures from ideal mathematical spectra.

The HNR here is the **known source power ratio** of the complete modulated tonal component (including its sidebands) to the noise component in the steady region. It is not an HNR estimated from the exported signal, nor a guarantee of perceived harmonicity. It remains fixed across other manipulations by the component-scaling rule.

## Loudness and remaining confounds

**These files are not yet loudness-matched or ready for the magnitude-estimation experiment.** Matching digital RMS only removes one physical-level difference. Listening comparisons, a playback calibration, and perceptual loudness matching remain necessary; do not describe these stimuli as equally loud.

No MoSQITo loudness or roughness numbers are calculated from uncalibrated full-scale WAV units. Its [time-varying Zwicker loudness](https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.loudness.loudness_zwtv.loudness_zwtv.html) and [Daniel–Weber roughness](https://mosqito.readthedocs.io/en/latest/source/reference/mosqito.sq_metrics.roughness.roughness_dw.roughness_dw.html) APIs take pressure in Pa. A calibrated or explicitly assumed pressure mapping would be needed to interpret those model outputs. For these modulated stimuli, time-dependent loudness should be examined rather than only a stationary summary.

Changing one synthesis parameter does not isolate one perceptual attribute:

- **Pitch:** shifting every harmonic also moves the absolute spectral distribution; the fixed noise band then has a different relationship to the carrier.
- **Brightness:** redistributing fixed energy changes the fundamental amplitude as well as the upper spectrum. Spectral centroid is not a validated brightness scale.
- **Roughness:** 70 Hz AM depth is a controllable roughness candidate, not a measured roughness value. Sidebands alter the spectrum and may affect timbre and loudness; perceptual ordering needs checking for this low-frequency carrier.
- **Noisiness:** adding broadband noise changes spectral centroid, masking, modulation salience, and harmonicity together.
- **Pulsation:** the control is rate rather than strength. Faster pulsation need not feel stronger. AM adds sidebands, and combinations with fast AM and noise can affect roughness and loudness.

Higher values may be less pleasant: comfort and perceptual separation need to be assessed together. Constant noise/modulation in the shared reference is an unavoidable design tradeoff if all dimensions need lower and higher values around one reference. If that reference is too intrusive, revise its settings and all variants together; another design would require separate references.

## Reproduce, inspect, and revise

```sh
source .venv/bin/activate
python -m sonification_stimuli.study --config configs/exploratory_set.json --output outputs/exploratory_v1
python -m unittest discover -s tests -v
```

The output directory must be empty. To iterate, edit `configs/exploratory_set.json` and generate into `outputs/exploratory_v2`, preserving v1 for comparison. Duration, fades, seeds, reference settings, and all four level values are configurable. The generator validates all levels before rendering; they must bracket the reference in intended direction.

The output contains 21 WAVs with JSON sidecars, 21 waveform/spectrum plots, `manifest.csv` with decoded measurements, a resolved `specification.json`, a generator source snapshot, and five convenience tracks with `previews/timing.json`. Spectra show the noise band as well as carrier partials. Source diagnostics include harmonic phases/weights, realized source HNR, source correlation, envelope extrema, and normalization gain. Digital analysis includes RMS, sample peak, crest factor, DC, and power-weighted spectral centroid. These are synthesis checks and acoustic descriptors; no perceptual model measurements are claimed. The source snapshot supplements the project source and version pins; it is not a standalone environment archive.

Tests cover the 21-condition design, single configured changes, fixed seeds, exact steady RMS and source HNR, measured AM sidebands, parameter rejection, PCM export/checksums, and use of the identical reference segment in all previews. Publication requires archived source/dependencies, selected WAVs and sidecars, playback/calibration details, and validated loudness and manipulation checks.
