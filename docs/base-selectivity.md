# Proposed base-stimulus selectivity score

This is an operational, descriptive index for the current manipulation protocol.
It rewards separation of the target estimate and penalizes changes in unrelated
estimates. It does not measure pleasantness, perceptual independence or suitability
for representing a mental state. Weights and normalization are design choices.

## Formula

For each measured proxy `j`, use one shared scale `s_j`: the maximum observed
nonnegative value across all reference and endpoint measurements in the same
analysis cohort. Cohorts separate backend, reference SPL assumption, scorer and
recorded model/library versions. An all-zero proxy uses scale 1, with all known
changes remaining zero. This is dimensionless and invariant to a change of units,
and avoids dividing by each base's potentially near-zero reference.

For a manipulation targeting proxy `t`:

```
Target benefit T = (x_target,5 − x_target,1) / (2 × s_target)

Coupling C = sqrt(
    sum_j w_j × [(x_j,1 − x_j,ref)² + (x_j,5 − x_j,ref)²] / s_j²
    -----------------------------------------------------------------
                          2 × sum_j w_j
)

Selectivity G = T − λ × C
```

The coupling sum contains the unrelated proxies plus loudness, excluding the
target proxy. Squaring both endpoint deviations prevents opposite side effects
from cancelling. Signed target separation rewards the intended low-to-high order;
reversed endpoints yield negative benefit. The report additionally flags cases
where the reference is outside the ordered endpoints.

Default `λ = 1`: equal reward/penalty coefficients after normalization. The report
slider explores `λ = 0…3`. Higher `G` is better under the specified formula; negative
values mean the penalty exceeds the target benefit. Unresponsive, unchanged audio
has `T = C = G = 0`; zero is not an excellent score.

## Proxies and weighting

| Control | Target proxy |
| --- | --- |
| Pitch | Estimated f0 |
| Brightness | Sharpness |
| Roughness | Daniel–Weber roughness |
| Noisiness | Spectral flatness, 100–4,000 Hz |
| Pulse frequency | Dominant slow-envelope rate |
| Pulse depth | Slow-envelope RMS fraction |

Each domain has weight 1. When pulse frequency and depth are both included, each
has weight 0.5 so pulsation does not receive two votes in the overall score. If
only one is included, it has weight 1. Loudness has weight 1 in every coupling
penalty. The overall score is the domain-weighted mean of the per-control scores.
The same domain balancing applies to off-target proxy weights.

Centroid, digital RMS and crest factor remain available for inspection in the
original report but do not enter this index. Adding more correlated proxies would
otherwise change the relative weight of their underlying attributes. Sharpness,
flatness, periodicity and envelope variation remain imperfect proxies rather than
validated one-to-one representations of the named perceptual characteristics.

## Missing estimates and comparisons

**Common basis** uses only proxies with complete reference/low/high measurements
for every base and manipulation in the cohort. Controls whose target proxy is
unavailable are removed for *all* bases, including from coupling penalties. Loudness
must remain complete. This yields directly comparable scores on an explicitly
limited, identical measurement basis.

In the current dataset that basis is **brightness, roughness, noisiness and pulse
depth**. Pitch and pulse frequency are excluded because some periodicity/envelope
rate estimates are unavailable. This is a four-control comparison, not a score for
the complete original protocol.

**Full protocol** requires all six controls and all required proxies. A missing
value makes the affected control score unavailable; an incomplete set does not
receive an overall score. Coverage and missing proxy names are retained. Missing
values are never replaced by zero and incomplete sets are never averaged as if
complete. Inactive source frequency manipulations with valid unchanged estimates
have zero benefit and penalty and are marked inactive.

The common comparison has fixed inclusion criteria across bases. It can change
when new measurements are added. This and fitting shared scales mean scores and
rankings are **relative to this dataset**, not absolute quality thresholds.
Compare values only within the same cohort and basis. The JSON preserves scales,
weights, included/excluded proxies and source CSV checksum for reproducibility.

## Outputs

Open `outputs/endpoint-comparisons/analysis.html` and use its **Base selectivity**
section. The live comparison responds to λ and offers a CSV download with the
current settings, dataset checksum and normalization scales.

* `base-selectivity.png`: Matplotlib comparison at λ = 1 on the common basis.
  Green bars show target benefit, red bars show the negative coupling contribution,
  and dots show the net score. Every measurement run remains separate.
* `base-selectivity.csv`: per-control and overall scores for both bases of
  comparison, at λ = 1; unavailable values are empty.
* `base-selectivity.json`: full definition/version, fitted scales, cohort metadata,
  default results and missingness details.

The index is regenerated by the existing report/export workflow. Slider settings
do not rewrite the default PNG/CSV on disk; use the live download to archive an
alternative weight. Before using this index as a paper's selection criterion,
agree on the proxy set, normalization dataset and λ, and examine sensitivity to
these choices and the underlying listening results.
