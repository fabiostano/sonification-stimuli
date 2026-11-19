"""Proposed descriptive target-versus-coupling index; not a perceptual quality scale."""
import io
import math

PROXIES = {"pitch": "f0_hz", "brightness": "sharpness_acum", "roughness": "roughness_asper",
           "noisiness": "spectral_flatness_100_4000", "pulsation": "envelope_peak_hz",
           "pulse_depth": "slow_envelope_rms_fraction"}
LOUDNESS = "loudness_sone"


def domain_weights(targets):
    pulses = sum(target in ("pulsation", "pulse_depth") for target in targets)
    return {target: 1 / pulses if target in ("pulsation", "pulse_depth") else 1 for target in targets}


def complete(cell):
    return all(cell[key] is not None and math.isfinite(cell[key]) and cell[key] >= 0
               for key in ("reference", "level_1", "level_5"))


def calculate_control(item, target, targets, scales):
    primary = next(cell for cell in item["cells"] if cell["target"] == target and cell["metric"] == PROXIES[target])
    features = {PROXIES[key]: weight for key, weight in domain_weights(targets).items() if key != target}
    features[LOUDNESS] = 1.0
    cells = {cell["metric"]: cell for cell in item["cells"] if cell["target"] == target}
    missing = [key for key in [PROXIES[target], *features] if not complete(cells[key])]
    if missing:
        return {"target": target, "available": False, "missing": missing, "benefit": None, "coupling": None, "score": None}
    scale = scales[PROXIES[target]]
    benefit = (primary["level_5"] - primary["level_1"]) / (2 * scale)
    squared = sum(weight * sum(((cells[key][f"level_{level}"] - cells[key]["reference"]) / scales[key]) ** 2
                               for level in (1, 5)) for key, weight in features.items())
    coupling = math.sqrt(squared / (2 * sum(features.values())))
    return {"target": target, "available": True, "missing": [], "benefit": benefit,
            "coupling": coupling, "score": benefit - coupling,
            "ordered": primary["level_1"] <= primary["reference"] <= primary["level_5"],
            "active": primary["active_1"] or primary["active_5"]}


def evaluate_cohort(items, targets, scales):
    result = []
    weights = domain_weights(targets)
    for item in items:
        controls = [calculate_control(item, target, targets, scales) for target in targets]
        usable = [control for control in controls if control["available"]]
        available = bool(targets) and len(usable) == len(targets)
        benefit = sum(weights[cell["target"]] * cell["benefit"] for cell in usable) / sum(weights.values()) if available else None
        coupling = sum(weights[cell["target"]] * cell["coupling"] for cell in usable) / sum(weights.values()) if available else None
        result.append({"set_id": item["id"], "label": item["label"], "mode": item["mode"],
                       "created": item["created"], "controls": controls, "available": available,
                       "coverage": len(usable), "required": len(targets), "benefit": benefit,
                       "coupling": coupling, "score": benefit - coupling if available else None})
    return {"targets": list(targets), "weights": weights, "bases": result}


def build_selectivity(dataset):
    cohorts = {}
    for item in dataset["sets"]:
        key = (item["backend"], item["spl"], item.get("model_version_signature", ""))
        cohorts.setdefault(key, []).append(item)
    result = []
    metric_keys = [*PROXIES.values(), LOUDNESS]
    for index, (identity, items) in enumerate(cohorts.items()):
        scales, excluded = {}, {}
        for key in metric_keys:
            values = [cell[field] for item in items for cell in item["cells"] if cell["metric"] == key
                      for field in ("reference", "level_1", "level_5") if cell[field] is not None and cell[field] >= 0]
            scales[key] = max(values, default=0) or 1.0
            missing = sum(not complete(cell) for item in items for cell in item["cells"] if cell["metric"] == key)
            if missing:
                excluded[key] = missing
        common = [target for target, key in PROXIES.items() if key not in excluded]
        # Loudness is a mandatory control, including in the common-basis view.
        if LOUDNESS in excluded:
            common = []
        result.append({"id": str(index), "backend": identity[0], "spl": identity[1],
                       "model_versions": identity[2], "scales": scales, "excluded": excluded,
                       "set_ids": [item["id"] for item in items],
                       "common": evaluate_cohort(items, common, scales),
                       "full": evaluate_cohort(items, list(PROXIES), scales)})
    return {"version": "proposed-selectivity-1.0", "default_penalty": 1.0,
            "scale_rule": "Maximum observed nonnegative value per metric within each backend/SPL/model-version cohort; all-zero scales use 1 (all changes remain zero).",
            "cohorts": result}


def comparison_png(result):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    fig, axes = plt.subplots(len(result["cohorts"]), 1, figsize=(11, 2.6 + 1.0 * max(len(c["common"]["bases"]) for c in result["cohorts"]) * len(result["cohorts"])), squeeze=False)
    for ax, cohort in zip(axes.flat, result["cohorts"]):
        bases = sorted(cohort["common"]["bases"], key=lambda item: item["score"] if item["score"] is not None else -math.inf, reverse=True)
        y = np.arange(len(bases))
        available = [i for i, item in enumerate(bases) if item["available"]]
        ax.barh([y[i] for i in available], [bases[i]["benefit"] for i in available], height=.5, color="#2b8b76", label="Target benefit T")
        ax.barh([y[i] for i in available], [-bases[i]["coupling"] for i in available], height=.5, color="#bd7778", label="Coupling penalty −C")
        ax.scatter([bases[i]["score"] for i in available], [y[i] for i in available], color="#243d48", s=65, zorder=4, label="Net score T − C")
        for i, item in enumerate(bases):
            label = f"  {item['score']:+.3f}" if item["score"] is not None else "not available"
            ax.annotate(label, (item["score"] or 0, y[i]), xytext=(7, -15), textcoords="offset points", fontsize=10)
        ax.set_yticks(y, [item["label"] for item in bases])
        ax.invert_yaxis()
        ax.axvline(0, color="#65777c", linewidth=.8)
        ax.grid(axis="x", alpha=.15)
        ax.set_axisbelow(True)
        ax.set_xlabel("Cohort-normalized score · higher is better under this formula")
        ax.set_title(f"Common basis: {', '.join(target.replace('_', ' ') for target in cohort['common']['targets'])}\n{cohort['backend']} · {cohort['spl']:g} dB SPL assumption · penalty weight λ = 1", fontsize=11)
        ax.legend(loc="upper center", bbox_to_anchor=(.5, -.17), ncol=3, frameon=False)
    fig.suptitle("Base-stimulus selectivity: target change versus unintended changes", fontsize=14)
    fig.text(.5, .012, "Proposed descriptive index, not a validated quality measure. Shared scales are fitted to this dataset.\nMissing estimates are excluded on the same basis for every base; model backends and assumptions are not pooled.", ha="center", fontsize=9)
    fig.tight_layout(rect=(0, .06, 1, .95), h_pad=5)
    output = io.BytesIO()
    fig.savefig(output, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output.getvalue()
