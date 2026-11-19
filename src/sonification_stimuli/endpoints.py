"""Save endpoint comparisons in the research project, or archive exact browser CSVs.

Run: python -m sonification_stimuli.endpoints --drone
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
import uuid

import numpy as np
from scipy.signal import resample_poly
import soundfile as sf

PROJECT = Path(__file__).resolve().parents[2]
DEFAULT_SITE = PROJECT / "sites/stimulus-explorer"
DEFAULT_OUTPUT = PROJECT / "outputs/endpoint-comparisons"
DIMENSIONS = ("pitch", "brightness", "roughness", "noisiness", "pulsation", "pulse_depth")
CONDITIONS = {("reference", 3)} | {(key, level) for key in DIMENSIONS for level in (1, 5)}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_table(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, strict=True)
        required = {"batch_id", "created_at_utc", "target_characteristic", "condition_level",
                    "wav_sha256", "model_status", "assumed_reference_spl_db",
                    "loudness_sone", "roughness_asper", "sharpness_acum"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: not an endpoint export (required columns missing)")
        rows = list(reader)
    groups = {}
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"{path}: malformed CSV row")
        try:
            condition = (row["target_characteristic"], int(row["condition_level"]))
            if not 40 <= float(row["assumed_reference_spl_db"]) <= 80:
                raise ValueError("invalid SPL assumption")
            if len(row["wav_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in row["wav_sha256"]):
                raise ValueError("invalid WAV checksum")
            if row.get("input_mode", "source") not in ("source", "drone"):
                raise ValueError("invalid input mode")
            for index, dimension in enumerate(DIMENSIONS):
                if int(row[f"setting_{dimension}_level"]) != (condition[1] if condition[0] == dimension else 3):
                    raise ValueError("not a one-control endpoint condition")
        except (KeyError, ValueError) as error:
            raise ValueError(f"{path}: invalid endpoint row: {error}") from error
        groups.setdefault((row["batch_id"], row["created_at_utc"]), []).append(condition)
    if not groups or any(len(values) != 13 or set(values) != CONDITIONS for values in groups.values()):
        raise ValueError(f"{path}: each measurement set must have one reference and twelve endpoints")
    return rows


def atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".endpoint-", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def inferred_backend(row):
    if row.get("analysis_backend"):
        return row["analysis_backend"]
    try:
        engine = json.loads(row.get("model_metadata_json") or "{}").get("runtime", {}).get("engine")
    except (ValueError, TypeError):
        engine = None
    return {"Pyodide": "browser-pyodide", "CPython": "native-cpython"}.get(engine, "imported-unknown")


def combine(output):
    """Rebuild the project table; preserve reruns and deduplicate exact imports."""
    measurements = {}
    for path in sorted(Path(output).glob("*-endpoints-*.csv")):
        for original in read_table(path):
            row = dict(original)
            row.setdefault("input_mode", "source")  # Historical browser source tables.
            if not row.get("base_id"):
                row["base_id"] = row.get("source_id", "")
            row["analysis_backend"] = inferred_backend(row)
            key = tuple(row[name] for name in ("batch_id", "created_at_utc", "target_characteristic", "condition_level"))
            if key in measurements:
                previous = measurements[key]
                if any(previous.get(name, "") != row.get(name, "") for name in previous.keys() | row.keys()):
                    raise ValueError(f"Conflicting measurements for {key}; per-base files are preserved")
                row = {**previous, **row}
            measurements[key] = row
    if not measurements:
        raise ValueError("No complete endpoint exports found")
    rows = list(measurements.values())
    columns = list(dict.fromkeys(key for row in rows for key in row))
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    path = Path(output) / "all-endpoint-comparisons.csv"
    atomic_write(path, handle.getvalue().encode("utf-8-sig"))
    return path, len(rows)


def archive_browser_csv(source, output):
    source, output = Path(source).resolve(), Path(output)
    rows = read_table(source)
    digest = sha256(source)
    destination = output / f"browser-import-endpoints-{digest[:24]}.csv"
    if destination.exists() and sha256(destination) != digest:
        raise ValueError(f"Destination conflict: {destination}")
    atomic_write(destination, source.read_bytes())  # Exact original bytes, including BOM/quoting.
    manifest = {"kind": "unchanged CSV import", "original_file": str(source),
                "sha256_csv": digest, "rows": len(rows),
                "imported_at_utc": datetime.now(timezone.utc).isoformat()}
    atomic_write(destination.with_suffix(".json"), (json.dumps(manifest, indent=2) + "\n").encode())
    return destination


def decode_source(path, start=0.0, duration=None):
    path = Path(path).resolve()
    if path.suffix.lower() not in (".wav", ".mp3"):
        raise ValueError(f"{path}: choose WAV or MP3")
    if path.stat().st_size > 25 * 1024**2:
        raise ValueError(f"{path}: source exceeds the app's 25 MB limit")
    info = sf.info(path)
    if info.channels not in (1, 2) or not 4 <= info.duration <= 180:
        raise ValueError(f"{path}: require mono/stereo, 4 seconds to 3 minutes")
    if not math.isfinite(start) or start < 0:
        raise ValueError("Excerpt start must be finite and nonnegative")
    duration = min(12.0, info.duration - start) if duration is None else duration
    if not math.isfinite(duration) or not 4 <= duration <= 30 or start + duration > info.duration + .0001:
        raise ValueError(f"{path}: choose a contained 4–30 second excerpt")
    decoded, fs = sf.read(path, dtype="float64", always_2d=True)
    mono = decoded.mean(axis=1)
    if fs != 48000:
        divisor = math.gcd(fs, 48000)
        mono = resample_poly(mono, 48000 // divisor, fs // divisor)
    # JavaScript Math.round for nonnegative values, including half-sample bounds.
    first = math.floor(start * 48000 + .5)
    count = min(math.floor(duration * 48000 + .5), len(mono) - first)
    digest = sha256(path)
    metadata = {"source_id": f"{digest[:16]}-{first}-{count}", "file_name": path.name,
                "file_sha256": digest, "excerpt_start_s": first / 48000,
                "excerpt_duration_s": count / 48000, "decoded_channels": info.channels,
                "decoded_sample_rate_hz": 48000, "downmix": "arithmetic channel mean",
                "reference_processing": "libsndfile decode; mono mean; SciPy polyphase resampling to 48 kHz; excerpt; shared renderer PCM-24 quantization"}
    decode = {"engine": "SoundFile/libsndfile + scipy.signal.resample_poly", "soundfile": sf.__version__,
              "libsndfile": sf.__libsndfile_version__, "original_sample_rate_hz": fs,
              "original_channels": info.channels, "sample_rate_hz": 48000,
              "resampling": "SciPy polyphase default Kaiser(5.0), constant-zero padding" if fs != 48000 else "none",
              "note": "Browser decode/resampling uses the browser implementation; exported WAV hashes can differ."}
    return np.asarray(mono[first:first + count], dtype="<f8"), metadata, decode


def load_scorer(site):
    path = Path(site) / "dist/psychoacoustics.py"
    spec = importlib.util.spec_from_file_location("endpoint_psychoacoustics", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module._load_models()
    except ImportError as error:
        raise ValueError("Install the native models: .venv/bin/python -m pip install '.[analysis]'") from error
    return module


def generate(mode, source, args, node, scorer):
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    label = "drone" if mode == "drone" else "source-" + "".join(c if c.isascii() and (c.isalnum() or c in "-_") else "_" for c in source.stem)[:60]
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="endpoint-export-") as temporary:
        work = Path(temporary)
        request = {"mode": mode, "site_directory": str(args.site_directory.resolve()),
                   "work_directory": str(work), "reports_file": str(work / "reports.json"),
                   "models_file": str(work / "models.json"), "csv_file": str(work / "endpoints.csv"),
                   "created_at": now.isoformat(), "run_id": run_id, "assumed_spl_db": args.assumed_spl}
        if source is not None:
            samples, request["metadata"], request["decode"] = decode_source(source, args.start, args.duration)
            request["samples_file"] = str(work / "source.f64")
            samples.tofile(request["samples_file"])
        request_path = work / "request.json"
        request_path.write_text(json.dumps(request))
        bridge = PROJECT / "scripts/endpoint_bridge.mjs"
        subprocess.run([str(node), str(bridge), "render", str(request_path)], check=True)
        report = json.loads((work / "reports.json").read_text())
        models, cache = [], {}
        for index, item in enumerate(report["reports"]):
            stimulus = item["stimulus"]
            digest = stimulus["sha256_wav"]
            print(f"{label}: {index + 1}/13 {item['condition']['target']} level {item['condition']['level']}", flush=True)
            if digest not in cache:
                samples, fs = sf.read(item["wav_path"], dtype="float64")
                if sha256(item["wav_path"]) != digest:
                    raise ValueError("Rendered WAV checksum mismatch")
                model = scorer.score_signal(samples, fs, assumed_spl_db=args.assumed_spl,
                                            reference_rms=stimulus.get("reference_digital_rms", .15 / math.sqrt(2)),
                                            fade_s=0 if mode == "source" else stimulus["config"]["carrier"]["fade_s"],
                                            f0_search_hz=(50, 2000) if mode == "source" else (100, 400),
                                            include_series=False)
                model["runtime"] = {"engine": "CPython", "python": platform.python_version()}
                cache[digest] = model
            models.append(cache[digest])
        (work / "models.json").write_text(json.dumps(models, allow_nan=False))
        subprocess.run([str(node), str(bridge), "csv", str(request_path)], check=True)
        rows = read_table(work / "endpoints.csv")
        destination = output / f"{label}-endpoints-{run_id}.csv"
        manifest = {"input_mode": mode, "analysis_backend": "native-cpython", "base_id": report["base_id"],
                    "batch_id": report["batch_id"], "run_id": run_id, "created_at_utc": now.isoformat(),
                    "sha256_csv": sha256(work / "endpoints.csv"), "rows": len(rows),
                    "source_file": str(source.resolve()) if source else None, "decode": request.get("decode"),
                    "node": subprocess.check_output([str(node), "--version"], text=True).strip(),
                    "python": platform.python_version(), "assumed_reference_spl_db": args.assumed_spl,
                    "code_sha256": {name: sha256(args.site_directory / "dist" / name) for name in
                                    ("synthesis.mjs", "source-audio.mjs", "endpoint-audit.mjs", "psychoacoustics.py")}}
        if args.save_wavs:
            wav_directory = output / (destination.stem + "-wavs")
            wav_directory.mkdir()
            for item in report["reports"]:
                condition = item["condition"]
                shutil.copyfile(item["wav_path"], wav_directory / f"{condition['target']}-{condition['level']}.wav")
            manifest["wav_directory"] = wav_directory.name
        atomic_write(destination, (work / "endpoints.csv").read_bytes())
        atomic_write(destination.with_suffix(".json"), (json.dumps(manifest, indent=2) + "\n").encode())
        print(f"Saved {destination}", flush=True)
        return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drone", action="store_true", help="Export the app's shared drone reference and endpoints")
    parser.add_argument("--source", nargs="+", action="extend", type=Path, default=[], help="Local WAV/MP3 files; first 12 seconds by default")
    parser.add_argument("--import-csv", nargs="+", action="extend", type=Path, default=[], help="Archive exact browser-downloaded CSVs; no Node/models required")
    parser.add_argument("--start", type=float, default=0, help="Source excerpt start in seconds")
    parser.add_argument("--duration", type=float, help="Source excerpt duration, 4–30 seconds; does not change drone duration")
    parser.add_argument("--assumed-spl", type=float, default=60, help="Reference SPL assumption, 40–80 dB; not playback calibration")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--site-directory", type=Path, default=DEFAULT_SITE)
    parser.add_argument("--node", type=Path, help="Node.js binary (PATH or project .tools/node/bin/node by default)")
    parser.add_argument("--save-wavs", action="store_true", help="Also keep the 13 exact WAVs scored per base")
    args = parser.parse_args(argv)
    if not (args.drone or args.source or args.import_csv):
        args.drone = True
    if not math.isfinite(args.assumed_spl) or not 40 <= args.assumed_spl <= 80:
        parser.error("--assumed-spl must be finite and in [40,80]")
    try:
        node = args.node or shutil.which("node") or PROJECT / ".tools/node/bin/node"
        if args.drone or args.source:
            if not Path(node).is_file():
                raise ValueError("Native generation requires Node.js 22 on PATH, in .tools/node/bin/node, or via --node")
            scorer = load_scorer(args.site_directory)
            if args.drone:
                generate("drone", None, args, node, scorer)
                combine(args.output_dir)
            for source in args.source:
                generate("source", source, args, node, scorer)
                combine(args.output_dir)
        for source in args.import_csv:
            print(f"Archived {archive_browser_csv(source, args.output_dir)}", flush=True)
        combined, count = combine(args.output_dir)
        print(f"Combined {count} rows: {combined}", flush=True)
        from .endpoint_report import generate_report
        report = generate_report(combined, args.output_dir)
        print(f"Offline analysis: {report['html']}", flush=True)
    except (OSError, ValueError, csv.Error, subprocess.CalledProcessError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
