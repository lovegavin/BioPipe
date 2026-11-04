# Normalize a numeric matrix

## Purpose

Transform numeric values using a declared normalization method while preserving
dimension names and labels. Choose the method from assay assumptions; these
methods are not interchangeable measures of biological abundance.

## Inputs and outputs

The input is a numeric Form with named dimensions and a missing-value convention.
The chosen `dim` identifies sample units. The remaining axes are flattened into
the values normalized within each sample. The output keeps the original shape
and labels and identifies its representation as `normalize`.

## Parameter guidance

Choose `method` explicitly: `cpm`, `total`, `median_of_ratios`, `quantile`, or
`zscore`. Set `dim` to the sample axis. `cpm` uses the positive `target_sum` setting;
it does not convert raw counts into transcript-length-normalized TPM. `zscore`
standardizes values within each selected sample. Inspect generated schema bounds
and parameter defaults before constructing a workflow.

## Interpretation

Inspect the exported per-sample before/after summaries and, where applicable,
size factors. Differences after normalization reflect the selected transformation
as well as biology. Preserve original data and record the method in the workflow.

## Limitations

The implementation declares full-memory execution. Missing entries are handled
according to the input convention and propagated as NaN. Zero totals, constant
samples and distributional differences require careful interpretation. No method
here automatically establishes that batch effects or confounding have been removed.

## Examples

`examples/documented_operators/run_example.py` provides a tested synthetic CSV ->
zscore -> PCA example. Its method is chosen to demonstrate the interface; use an
assay-appropriate alternative for scientific data.
