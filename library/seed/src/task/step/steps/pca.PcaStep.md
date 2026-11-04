# Principal component analysis

## Purpose

Summarize variation in a two-dimensional numeric matrix using principal component
scores. Use this to inspect sample relationships and potential outliers; a visual
separation alone does not establish a biological mechanism or statistical result.

## Inputs and outputs

The input must have two named dimensions, numeric values and `missing_code` in
its info. With `dim="feature"`, samples remain observations and features are
compressed into the output `component` dimension. Sample labels are preserved.

## Parameter guidance

Set `dim` to the axis being compressed, normally `feature`. `n_components` is one
integer, not a comma-separated list of dimensions. The implementation caps this
at the smaller matrix dimension. Use the generated parameter section for current
defaults; saved workflow values remain independent.

## Interpretation

The implementation replaces missing values with each feature's mean, centers
features and divides by their standard deviation before SVD. Constant or fully
missing features receive safe fallback scales; assess their prevalence during QC.
Scores are singular-vector coordinates scaled by singular values. Component signs
are arbitrary, so compare geometry or variance, not a required positive sign.

## Limitations

The current implementation uses a full dense SVD and declares full-memory
execution. Disk-backed input does not make the SVD itself streaming. Scaling gives
features comparable variance, which may amplify low-information features. Apply
assay-appropriate filtering and transformation before interpreting the plot.

## Examples

The executable synthetic example is `examples/documented_operators/run_example.py`.
Run `python -m examples.documented_operators.run_example ./example-output` from the
repository root. It checks a compressed CSV -> normalize -> PCA pipeline and
preserves sample labels. Its input is synthetic, not an analysis recommendation.
