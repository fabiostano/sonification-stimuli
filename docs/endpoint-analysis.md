# Explore manipulation effects

Open `outputs/endpoint-comparisons/analysis.html` in a browser, including by
double-clicking it. No server, account, installation or internet connection is
needed to view it. The file embeds its data and overview figure, so it can be
copied to a coauthor as one self-contained file.

## Reading the report

1. Choose a **base / measurement run**. Runs, model assumptions and analysis
   backends remain separate.
2. Read the **What else changes?** matrix. Rows identify the manipulated control
   and endpoint (1 or 5); columns identify measured properties. Switch between
   percentages, changes in original units, or raw measured values.
3. Click a cell, or choose a manipulation and property. **Compare across bases**
   displays the level-1, reference and level-5 measurements for every base/run,
   with signed and percentage changes. The selected base's actual manipulation
   settings are shown above the table and in matrix-cell tooltips.
4. Expand the overview to download its PNG or the tidy summary CSV. These are
   also saved beside the report as `manipulation-overview.png` and
   `manipulation-summary.csv`.

Related target proxies are outlined for convenience: estimated f0 for pitch,
sharpness for brightness, modeled roughness for roughness, spectral flatness for
noisiness, envelope rate for pulse frequency, and slow-envelope RMS fraction for
depth. These are not validated one-to-one perceptual mappings. The other columns
make off-target changes visible, including loudness, centroid and digital level.

Colours use percentage change on the **same fixed −100% to +100% scale**. More
extreme values retain their numbers while colours saturate. This avoids making
tiny numerical changes appear large by rescaling each column independently.
Colours retain this meaning even when the displayed numbers use original units.
Negative changes are blue and positive changes red; neither colour means good or
bad. dB columns display dB differences and remain uncoloured. Missing values and
zero-reference percentages stay unavailable. Large percentages from small
reference values can be misleading; inspect the raw measurements too.

Source pulse-frequency endpoints are explicitly marked inactive at reference
depth. Their zero changes are valid measurements of unchanged audio, rather
than missing values. Drone frequency endpoints are active at depth 0.25.

## Regenerate

```sh
.venv/bin/python -m sonification_stimuli.endpoint_report

# Or analyze another complete endpoint CSV:
.venv/bin/python -m sonification_stimuli.endpoint_report \
  --csv /path/to/comparisons.csv --output-dir outputs/my-analysis
```

After local endpoint generation or CSV import completes successfully, the export
command automatically refreshes these reports. Regenerating the report never
resynthesizes audio or recalculates psychoacoustic scores. It reads the stored
measurements and recomputes descriptive differences from each set's reference.

The tidy summary has one row per measurement set × manipulated control × measured
property (300 rows for the current five sets, six controls and ten properties).
It includes raw values, differences, the high-minus-low contrast, percentages,
settings, activity flags, model backend and sound-level assumption. Missing
values remain empty. The HTML footer records its source CSV checksum and build
time. The overview is drawn using Matplotlib and saved as a standalone PNG.

These are descriptive checks of single rendered examples. There are no
participant responses, uncertainty estimates or significance tests. The report
does not average different bases/backends together or establish perceptual
independence. Acoustic and model interactions can motivate stimulus
refinement; they do not establish how listeners perceive the manipulations.

The report now also includes an explicitly proposed **base selectivity index**,
with adjustable target-versus-coupling trade-off, common/full comparison bases and
separate default score exports. This is a descriptive operational score rather
than a perceptual independence measure. See [its formula, weights and limitations](base-selectivity.md).
