# CSV Reader

## Purpose

Read a delimited two-dimensional table into a Form with dimension names, labels
and missing-value information. Compressed `.csv.gz`, `.csv.bz2` and `.csv.xz`
inputs use the same Reader; decompression is handled by the reading layer.

## Inputs and outputs

Provide the file path and two dimensions, commonly `sample` and `feature`.
The default treats the first line as a header. The output includes numeric values,
axis label maps and `missing_code`; nonnumeric columns can be encoded and their
encoders recorded. Review such columns before using numeric statistical methods.

## Parameter guidance

Use the generated schema for delimiter, header, selected columns and info-column
options. `header=false` reads every line as data. A `builtin` label rule reads the
column header; `auto` generates positional labels. A label rule selecting a column
uses its position in the original file, even when `columns` selects a subset.
Use `info_columns` to retain annotation strings as axis-aligned metadata instead
of including them in the numeric matrix.

## Interpretation

Check feature names, sample IDs, missing values and encoding metadata after
reading. Successful parsing does not establish assay units, normalization status,
or whether categorical columns are scientifically meaningful as numeric inputs.

## Limitations

This Reader currently declares full-memory loading. Compression reduces storage
size but does not guarantee a small dense matrix. Operon's runtime budgets and
spill mechanisms remain active; downstream full-memory algorithms still need
their working set. Duplicate labels are disambiguated with positional suffixes.

## Examples

`examples/documented_operators/run_example.py` creates and reads a compressed CSV
with feature headers, then runs normalization and PCA. It verifies that sample
labels survive the workflow and stores the synthetic results as JSON.
