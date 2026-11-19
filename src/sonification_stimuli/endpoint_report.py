"""Create an offline, interactive manipulation report and a Matplotlib overview."""
import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path

from .endpoints import DEFAULT_OUTPUT, DIMENSIONS, atomic_write, inferred_backend, read_table

METRICS = [
    ("f0_hz", "Estimated f0", "Hz", "pitch"),
    ("sharpness_acum", "Sharpness", "acum", "brightness"),
    ("roughness_asper", "Roughness", "asper", "roughness"),
    ("spectral_flatness_100_4000", "Spectral flatness", "ratio", "noisiness"),
    ("envelope_peak_hz", "Envelope rate", "Hz", "pulsation"),
    ("slow_envelope_rms_fraction", "Envelope variation", "ratio", "pulse_depth"),
    ("loudness_sone", "Loudness", "sone", None),
    ("power_centroid_hz", "Power centroid", "Hz", None),
    ("steady_rms_dbfs", "Steady/excerpt RMS", "dBFS", None),
    ("crest_factor_db", "Crest factor", "dB", None),
]
LABELS = {"pitch": "Pitch", "brightness": "Brightness", "roughness": "Roughness",
          "noisiness": "Noisiness", "pulsation": "Pulse frequency", "pulse_depth": "Pulse depth"}


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def metric_value(row, key):
    if row.get(key + "_status") not in (None, "", "ok"):
        return None
    return number(row.get(key))


def difference(value, reference):
    return value - reference if value is not None and reference is not None else None


def percentage(value, reference, unit):
    if unit in ("dB", "dBFS") or value is None or reference is None or reference == 0:
        return None
    return 100 * (value - reference) / abs(reference)


def reference_setting(row, target, mode):
    if mode == "source":
        return f"{row['control_slow_am_hz']} Hz (inactive)" if target == "pulsation" and row.get("control_slow_am_hz") else "Original"
    key, unit = {"pitch": ("fundamental_hz", "Hz"), "brightness": ("harmonic_decay", "decay"),
                 "roughness": ("roughness_depth", "fast AM depth"), "noisiness": ("source_hnr_db", "dB HNR"),
                 "pulsation": ("pulsation_hz", "Hz"), "pulse_depth": ("slow_am_depth", "slow AM depth")}[target]
    value = row.get("control_" + key)
    return f"{value} {unit}" if value else "Reference"


def build_dataset(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault((row["batch_id"], row["created_at_utc"]), []).append(row)
    sets, tidy = [], []
    for identity, members in grouped.items():
        reference = next(row for row in members if row["target_characteristic"] == "reference")
        backend = inferred_backend(reference)
        mode = reference.get("input_mode") or "source"
        spl = number(reference["assumed_reference_spl_db"])
        for row in members:
            if inferred_backend(row) != backend or (row.get("input_mode") or "source") != mode or number(row["assumed_reference_spl_db"]) != spl:
                raise ValueError("A measurement set mixes backend, base mode, or SPL assumptions")
        label = reference.get("base_label") or reference.get("source_file") or "Harmonic drone"
        try:
            model = json.loads(reference.get("model_metadata_json") or "{}")
        except ValueError:
            model = {}
        model_signature = json.dumps({"scorer": reference.get("scorer_version", ""), "packages": model.get("versions", {})}, sort_keys=True)
        set_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:16]
        cells = []
        for target in DIMENSIONS:
            conditions = {int(row["condition_level"]): row for row in members if row["target_characteristic"] == target}
            for key, name, unit, proxy in METRICS:
                ref, low, high = (metric_value(row, key) for row in (reference, conditions[1], conditions[5]))
                item = {"set_id": set_id, "base_label": label, "input_mode": mode,
                        "analysis_backend": backend, "assumed_reference_spl_db": spl,
                        "created_at_utc": identity[1], "target": target, "metric": key,
                        "metric_label": name, "unit": unit, "target_proxy": proxy == target,
                        "reference": ref, "level_1": low, "level_5": high,
                        "delta_1": difference(low, ref), "delta_5": difference(high, ref),
                        "percent_1": percentage(low, ref, unit), "percent_5": percentage(high, ref, unit),
                        "contrast_5_minus_1": difference(high, low),
                        "active_1": conditions[1].get("target_operation_active") != "false",
                        "active_5": conditions[5].get("target_operation_active") != "false",
                        "reason_1": conditions[1].get(key + "_reason", ""),
                        "reason_5": conditions[5].get(key + "_reason", ""),
                        "effect_1": conditions[1].get("target_effect", ""),
                        "effect_5": conditions[5].get("target_effect", ""),
                        "effect_reference": reference_setting(reference, target, mode),
                        "target_note": conditions[1].get("target_note") or conditions[5].get("target_note", "")}
                cells.append(item)
                tidy.append(item)
        sets.append({"id": set_id, "label": label, "mode": mode, "backend": backend,
                     "model_version_signature": model_signature,
                     "spl": spl, "created": identity[1], "batch_id": identity[0],
                     "duration_s": number(reference.get("excerpt_duration_s")),
                     "excerpt_start_s": number(reference.get("excerpt_start_s")),
                     "model_start_s": number(reference.get("model_analysis_start_s")),
                     "model_end_s": number(reference.get("model_analysis_end_s")),
                     "cells": cells})
    return {"sets": sets, "metrics": [{"key": key, "label": name, "unit": unit, "proxy": proxy} for key, name, unit, proxy in METRICS],
            "targets": [{"key": key, "label": LABELS[key]} for key in DIMENSIONS],
            "rows": len(rows)}, tidy


def overview_png(dataset):
    """All runs remain separate. Colours share a fixed +/-100% scale."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.cm import ScalarMappable
    import numpy as np

    metrics = dataset["metrics"][:8]
    sets = dataset["sets"]
    columns = min(2, len(sets))
    nrows = math.ceil(len(sets) / columns)
    fig, axes = plt.subplots(nrows, columns, figsize=(8.5 * columns, 6.7 * nrows), squeeze=False)
    cmap = plt.get_cmap("RdBu_r").copy()
    cmap.set_bad("#e8ecec")
    for index, item in enumerate(sets):
        ax = axes.flat[index]
        matrix = np.full((12, len(metrics)), np.nan)
        labels = []
        for target_index, target in enumerate(dataset["targets"]):
            for offset, level in enumerate((1, 5)):
                row_index = target_index * 2 + offset
                cells = [cell for cell in item["cells"] if cell["target"] == target["key"]]
                active = cells[0][f"active_{level}"]
                labels.append(f"{target['label']} {level}" + (" [inactive]" if not active else ""))
                for column, metric in enumerate(metrics):
                    cell = next(cell for cell in cells if cell["metric"] == metric["key"])
                    value = cell[f"percent_{level}"]
                    if value is not None and active:
                        matrix[row_index, column] = value
                    text = "inactive" if not active else "—" if value is None else f"{value:+.0f}%"
                    ax.text(column, row_index, text, ha="center", va="center", fontsize=7,
                            color="white" if value is not None and active and abs(value) > 65 else "#213436")
        ax.imshow(matrix, cmap=cmap, norm=Normalize(-100, 100), aspect="auto")
        ax.set_xticks(range(len(metrics)), [metric["label"] for metric in metrics], rotation=38, ha="right", fontsize=9)
        ax.set_yticks(range(12), labels, fontsize=9)
        ax.set_title(f"{item['label']}\n{item['backend']} · {item['spl']:g} dB SPL assumption\n{item['created']}", fontsize=10, pad=12)
        for boundary in (1.5, 3.5, 5.5, 7.5, 9.5):
            ax.axhline(boundary, color="white", linewidth=1.5)
    for ax in list(axes.flat)[len(sets):]:
        ax.set_visible(False)
    fig.suptitle("Endpoint changes relative to each base's reference", fontsize=17, y=.998)
    fig.text(.5, .008, "Colour capped at ±100%; labels show actual percentages. Grey: unavailable or inactive.\nLarge percentages near a zero reference need caution. Descriptive acoustic/model estimates, not perceptual independence.", ha="center", fontsize=10)
    fig.tight_layout(rect=(0, .035, .97, .975), h_pad=3, w_pad=3)
    color_ax = fig.add_axes((.975, .2, .009, .6))
    fig.colorbar(ScalarMappable(norm=Normalize(-100, 100), cmap=cmap), cax=color_ax, label="Change from reference (%)", extend="both")
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=120, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return output.getvalue()


def generate_report(csv_path, output_dir=None):
    csv_path = Path(csv_path).resolve()
    output_dir = Path(output_dir).resolve() if output_dir else csv_path.parent
    dataset, tidy = build_dataset(read_table(csv_path))
    dataset.update({"source_name": csv_path.name, "source_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
                    "generated_at": datetime.now(timezone.utc).isoformat()})
    from .selectivity import build_selectivity, comparison_png
    dataset["selectivity"] = build_selectivity(dataset)
    dataset["selectivity"].update(source_csv_sha256=dataset["source_sha256"], source_csv_name=csv_path.name)
    score_image = comparison_png(dataset["selectivity"])
    image = overview_png(dataset)
    template = (Path(__file__).parent / "templates/endpoint_report.html").read_text()
    # The JSON is data even if a source filename contains an HTML closing tag.
    payload = json.dumps(dataset, allow_nan=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    html = template.replace("__REPORT_DATA__", payload).replace("__OVERVIEW_PNG__", base64.b64encode(image).decode()).replace("__SELECTIVITY_PNG__", base64.b64encode(score_image).decode())
    summary = io.StringIO(newline="")
    writer = csv.DictWriter(summary, fieldnames=list(tidy[0]))
    writer.writeheader()
    writer.writerows(tidy)
    paths = {"html": output_dir / "analysis.html", "overview": output_dir / "manipulation-overview.png",
             "summary": output_dir / "manipulation-summary.csv", "selectivity_plot": output_dir / "base-selectivity.png",
             "selectivity_scores": output_dir / "base-selectivity.csv", "selectivity_spec": output_dir / "base-selectivity.json"}
    score_rows = []
    for cohort in dataset["selectivity"]["cohorts"]:
        for basis in ("common", "full"):
            for base in cohort[basis]["bases"]:
                metadata = {"cohort": cohort["id"], "basis": basis, "set_id": base["set_id"], "base_label": base["label"],
                            "backend": cohort["backend"], "assumed_spl_db": cohort["spl"], "penalty_weight": 1,
                            "coverage": base["coverage"], "required_controls": base["required"]}
                score_rows.append({**metadata, "target": "overall", "benefit": base["benefit"], "coupling": base["coupling"], "score": base["score"], "missing": "", "ordered": ""})
                for cell in base["controls"]:
                    score_rows.append({**metadata, "target": cell["target"], "benefit": cell["benefit"], "coupling": cell["coupling"], "score": cell["score"], "missing": ";".join(cell["missing"]), "ordered": cell.get("ordered")})
    score_csv = io.StringIO(newline="")
    score_writer = csv.DictWriter(score_csv, fieldnames=list(score_rows[0]))
    score_writer.writeheader()
    score_writer.writerows(score_rows)
    atomic_write(paths["html"], html.encode())
    atomic_write(paths["overview"], image)
    atomic_write(paths["summary"], summary.getvalue().encode("utf-8-sig"))
    atomic_write(paths["selectivity_plot"], score_image)
    atomic_write(paths["selectivity_scores"], score_csv.getvalue().encode("utf-8-sig"))
    atomic_write(paths["selectivity_spec"], (json.dumps(dataset["selectivity"], indent=2, allow_nan=False) + "\n").encode())
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_OUTPUT / "all-endpoint-comparisons.csv")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args(argv)
    try:
        paths = generate_report(args.csv, args.output_dir)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))
    for kind, path in paths.items():
        print(f"{kind}: {path}")


if __name__ == "__main__":
    main()
