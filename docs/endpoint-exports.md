# Endpoint CSVs in the browser and research project

The web app still automatically downloads per-base CSVs and retains completed
tables in browser storage. Its **All saved CSV** combines that browser's records.
The project now also supports local generation and exact import of browser CSVs.
The hosted app does not silently write to the local project folder.

All local exports are saved by default in `outputs/endpoint-comparisons/`:

* one uniquely named `*-endpoints-*.csv` per base/run, with an adjacent provenance
  JSON file;
* `all-endpoint-comparisons.csv`, rebuilt from complete local exports and imports;
* optional scored WAVs if `--save-wavs` is specified.

Successful export/import commands also refresh `analysis.html`,
`manipulation-overview.png` and `manipulation-summary.csv`. Open the HTML directly
in a browser for an offline interactive analysis; see the [analysis guide](endpoint-analysis.md).

Generated outputs and the local Node runtime are Git-ignored. Archive the selected
CSVs, JSON sidecars and source audio together for publication.

## Generate locally

From the project root, with its virtual environment:

```sh
# Shared middle drone + levels 1 and 5 of all six controls (13 rows).
.venv/bin/python -m sonification_stimuli.endpoints --drone

# One or several base recordings; first 12 seconds, 60 dB SPL assumption.
.venv/bin/python -m sonification_stimuli.endpoints --source \
  "stimuli/base stimuli/stim_amb_1.mp3" \
  "stimuli/base stimuli/stim_focus_1.mp3"

# Both base types, with source excerpt/model settings made explicit.
.venv/bin/python -m sonification_stimuli.endpoints --drone \
  --source "stimuli/base stimuli/stim_amb_1.mp3" \
  --start 0 --duration 12 --assumed-spl 60 --save-wavs
```

No flags defaults to `--drone`. `--duration` and `--start` apply to source excerpts;
drone duration and levels come from the same `data/live.json` used by the app.
Use `--output-dir` to choose a different archive directory. Existing per-base
exports are preserved on rerun; each run has a distinct timestamp and ID.

Native generation requires the project dependencies, pinned MoSQiTo 1.2.1/pyuff
2.5.1, and Node.js 22. This workspace has the model packages installed in `.venv`
and a local Node 22.14.0 at `.tools/node/bin/node`. The command discovers Node on
PATH or uses that project-local copy. On another machine:

```sh
.venv/bin/python -m pip install '.[analysis]'
# Install Node.js 22 on PATH, or supply --node /absolute/path/to/node.
```

The Python command calls the **same JavaScript synthesis, source effects,
endpoint design, CSV encoder and reference-change code** used by the web app.
It scores the exact exported PCM-24 samples using the app's Python model code
under CPython. Frozen-noise checksums are verified before synthesis. CSV sidecars
record renderer/scorer code checksums, run ID, backend, model level, Node/Python
versions, source decoder details and CSV checksum. Per-row model metadata retains
model/library versions, calibration, windows, errors and warnings.

Native output is explicitly labelled `analysis_backend=native-cpython` and uses
separate batch IDs. Native and browser floating-point model results are not
claimed to be identical. Native imports decode with SoundFile/libsndfile and use
SciPy's polyphase resampler when needed; browser decoding/resampling can produce
different reference samples, especially for MP3 or non-48 kHz audio. Each row
retains its actual WAV checksum and native decoding provenance. To preserve the
**exact browser results**, use the import route below rather than regenerating.

## Keep exact browser results in the project

Download **This drone CSV**, **This source CSV**, or **All saved CSV** in the app,
then provide the downloaded file path:

```sh
.venv/bin/python -m sonification_stimuli.endpoints --import-csv \
  "$HOME/Downloads/base-endpoint-comparison.csv"
```

This validates every complete 13-row set and its one-control endpoint settings,
then copies the original CSV **byte for byte** into the project. It does not
resynthesize audio or recalculate scores. This route does not require Node or the
optional model packages. An adjacent JSON records the original file path and
checksum. Reimporting the same file is idempotent.

The combined project CSV labels browser rows `analysis_backend=browser-pyodide`
when their model metadata identifies that runtime. Older source-only exports
are identified as `input_mode=source`. Other unknown backends remain explicitly
unknown. Exact duplicate measurements imported from both individual and combined
CSVs are deduplicated, including empty columns added by a combined export.
Distinct runs are retained. Conflicting values for the same batch/timestamp/
condition raise an error and preserve the previous combined file.

## Interpretation

Each base has one reference and levels 1 and 5 of pitch, brightness, roughness,
noisiness, pulse frequency, and pulse depth. All other controls stay at Reference.
The CSV contains actual estimates, reference values, signed changes and suitable
percentage changes. Missing values remain empty, with model/descriptor statuses.

Drone frequency endpoints are active at the reference depth of 0.25. Source
frequency endpoints remain inactive at original depth and are flagged. Models
summarize the central two seconds with 0.25 seconds of preceding warmup; drone
fades are excluded, source excerpts have no added fades. Each set uses one fixed
reference-RMS-to-pressure mapping. SPL is an assumption, not playback calibration,
and RMS matching does not establish equal perceived loudness.

See the app's [full CSV column guide](../sites/stimulus-explorer/dist/data/endpoint-methods.md).
