# Documented Reader/operator example

From the repository root:

```text
python -m examples.documented_operators.run_example ./example-output
```

The example creates a tiny compressed CSV, reads its feature labels, normalizes
each sample, and computes two principal components with the real SDK/engine.
The output directory contains `synthetic.csv.gz` and `result.json`. Numerical
checks cover finite scores, shape and sample-label preservation. These synthetic
data illustrate the interfaces and do not imply any biological conclusion.

`tests/test_operator_docs.py` executes the same example. For actual count data,
choose a normalization appropriate to the assay rather than copying the example
method automatically. See the `normalize`, `pca` and `CsvReader` documentation.
