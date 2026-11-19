# First timbre auditions

The initial drone is a viable candidate, but the listener described it as only moderately pleasant. This set explores three alternative harmonic envelopes before selecting a base sound. Names indicate intended timbral directions; they are not verified perceptual descriptions or claims of greater pleasantness.

All four candidates use f0 = 220 Hz, harmonic indices 1–8, 12 seconds, 0.75-second fades, 48 kHz mono PCM-24, gain = 0.15, and seed = 20261016. They retain the same initial phase for each harmonic index. There are no added effects, detuning, noise, or deliberate modulation. The original reference is preserved.

| Candidate | Relative harmonic amplitude before unit-L2 normalization | Intended comparison |
| --- | --- | --- |
| Original | `k^-1.5` | Initial reference |
| Soft harmonic | `k^-2.5` | Less upper-harmonic energy while keeping every partial |
| Rounded | `exp(-1.2*(k-1))` | Different rolloff shape; a second harmonic with a rapidly diminishing upper tail |
| Hollow | `k^-1.5` for odd k, zero for even k | Different spectral structure: fundamental plus third, fifth, seventh |

Here `harmonics = 8` means highest requested harmonic index, including zero-weight entries for the odd profile. The decay parameter has different meanings across profiles; its numeric values are not comparable brightness levels. Odd-only synthesis reduces the number of nonzero partials. The spectral changes intentionally alter several descriptors at once: these are candidate base timbres, not isolated experimental manipulations.

## Listen

From the project directory:

```sh
afplay outputs/reference.wav
afplay outputs/auditions/soft_harmonic.wav
afplay outputs/auditions/rounded.wav
afplay outputs/auditions/hollow.wav
```

Listen separately, then repeat in a different order. Use the same playback equipment and volume setting for the initial comparison. Note pleasantness, perceived loudness, whether it feels tiring or intrusive, and which sound you would tolerate in the background. A short audition cannot establish long-term comfort. If you adjust volume for comfort, record that adjustment rather than interpreting the result as a loudness-controlled comparison.

The weighting convention gives equal theoretical steady-state energy, **not equal perceived loudness**. Differences in spectral placement can change loudness. We have not matched these candidates perceptually. Holding f0 fixed helps focus this first comparison on timbre; lower/higher registers can be explored after identifying a preferred profile.

Each WAV has a JSON sidecar and waveform/spectrum PNG. To regenerate one candidate or change its register:

```sh
source .venv/bin/activate
drone --config configs/auditions/rounded.toml --output outputs/auditions/rounded.wav
drone --config configs/auditions/rounded.toml --f0 165 --output outputs/auditions/rounded-lower.wav
```

The second command is an optional exploration, not a proposed pitch level. Selecting a base will also require checking whether it can support useful brightness, roughness, noisiness, and pulsation manipulations. A nearly sinusoidal pleasant tone may leave little room for reducing brightness further.

## Rounded register comparison

The listener preferred the rounded candidate, which is now the provisional timbre. The next audition compares three registers spaced by approximately equal frequency ratios around the original. These are exploration points, not proposed experimental levels or a validated perceptual scale.

| Register | Fundamental | WAV |
| --- | --- | --- |
| Lower | 165 Hz | `outputs/auditions/register/rounded_165hz.wav` |
| Current | 220 Hz | `outputs/auditions/rounded.wav` (preserved) |
| Higher | 293.333333 Hz | `outputs/auditions/register/rounded_293hz.wav` |

The lower/current and current/higher frequency ratios are approximately 4:3. Only f0 changes: the eight harmonic indices, exponential decay of 1.2, per-index phases, gain of 0.15, 12-second duration, sample rate, and fades stay fixed. All partial frequencies shift together. This also shifts the absolute spectral centroid, and equal digital energy does not imply equal perceived loudness. No loudness compensation was applied.

Regenerate the two new files using the existing rounded configuration:

```sh
source .venv/bin/activate
drone --config configs/auditions/rounded.toml --f0 165 --output outputs/auditions/register/rounded_165hz.wav
drone --config configs/auditions/rounded.toml --f0 293.333333 --output outputs/auditions/register/rounded_293hz.wav
```

Listen one at a time:

```sh
afplay outputs/auditions/register/rounded_165hz.wav
afplay outputs/auditions/rounded.wav
afplay outputs/auditions/register/rounded_293hz.wav
```

Then try the reverse order. Note which register is most comfortable, whether any feels more intrusive, and whether one seems noticeably louder. Keep the initial playback volume fixed; record any comfort adjustments. Each new file includes its resolved configuration, measurements, checksum, and waveform/spectrum plot in adjacent JSON/PNG files.

## Rounded timbre refinement at 220 Hz

The listener found all three registers acceptable, with the higher register somewhat less comfortable. There was no clear preference between 165 and 220 Hz, so 220 Hz remains the provisional base. This does not establish a final pitch range.

Two new candidates flank the existing exponential decay of 1.2. The only configuration change is `harmonic_decay`. All eight partials remain present at the same frequencies and initial phases; gain, duration, fades, and sample rate remain fixed.

| Candidate | Exponential decay | Second/fundamental amplitude ratio | WAV |
| --- | --- | --- | --- |
| Softer | 1.45 | 0.235 | `outputs/auditions/refinement/rounded_softer.wav` |
| Current | 1.20 | 0.301 | `outputs/auditions/rounded.wav` |
| Fuller | 0.95 | 0.387 | `outputs/auditions/refinement/rounded_fuller.wav` |

Relative weights are `exp(-decay*(k-1))`, followed by unit-L2 normalization. Increasing decay reduces upper-harmonic energy; normalization also increases the fundamental's absolute amplitude. Decreasing decay does the reverse. This is redistribution of fixed theoretical energy, not an isolated change to upper partials with the fundamental held constant. Perceived loudness may still differ. The names describe intended directions, not validated perceptual attributes, and these values are not proposed experimental brightness levels.

Regenerate and listen:

```sh
source .venv/bin/activate
drone --config configs/auditions/rounded_softer.toml --output outputs/auditions/refinement/rounded_softer.wav
drone --config configs/auditions/rounded_fuller.toml --output outputs/auditions/refinement/rounded_fuller.wav
afplay outputs/auditions/refinement/rounded_softer.wav
afplay outputs/auditions/rounded.wav
afplay outputs/auditions/refinement/rounded_fuller.wav
```

Repeat in reverse order at the same playback setting. Note comfort, intrusiveness, apparent loudness, and whether the difference is noticeable. Retaining the current version is a valid outcome if neither alternative is clearly preferable. The two new WAVs have adjacent JSON measurements and PNG plots; earlier candidates are preserved.
