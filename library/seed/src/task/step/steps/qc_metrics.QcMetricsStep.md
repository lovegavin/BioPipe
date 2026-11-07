<!-- operon:generated -->
# qc_metrics

## Purpose

> Per-sample summary metrics along a feature axis.
>
> Input: any 2D Form with axes [feature_dim, sample_dim].
>
> For each declared metric, a summary is computed along the feature
> axis, producing one value per sample. A metric may restrict itself
> to features whose label starts with a given prefix, and may divide
> its raw result by another metric declared in the same call.
>
> Metrics
> -------
> op values and their meaning over the selected feature subset:
>     sum      sum of non-missing values
>     mean     arithmetic mean of non-missing values
>     std      population standard deviation (ddof=0)
>     var      population variance (ddof=0)
>     min      minimum of non-missing values
>     max      maximum of non-missing values
>     count    number of non-missing values
>     nonzero  number of non-missing and non-zero values
>
> Missing cells are recognised from info["missing_code"]: when that
> code is NaN, non-finite cells count as missing.
>
> Output:
>     data   2D float32, shape (n_samples, n_metrics)
>     dims   [sample_dim, statistic]
>     statistic labels are the metric names, in declaration order.
>
> Params:
>     feature_dim : feature axis (default "feature")
>     sample_dim  : sample axis  (default "sample")
>     metrics     : list of {"name", "op", "feature_pattern"?, "divide_by"?}
>     output      : context key (default: step name)

## Inputs and outputs

Kind: `operator`. Operator ID: `qc_metrics`.
Input count: `1`.
Read the structured `contracts` section before connecting nodes. It includes
the accepted data types, dimension constraints and output propagation rule.

## Parameter guidance

The adjacent parameter JSON owns defaults, valid choices, ranges and required
fields. Request the generated `parameters` section and `parameters_schema` for
the exact interface; do not infer parameter names from prose.
Saved routes keep their own parameter values independently of current defaults.

## Interpretation

Check output metadata and labels before downstream analysis. The declared output
contract describes the representation; it does not establish biological validity
or statistical assumptions for a particular dataset.

## Runtime environment

Runs in the shared Operon interpreter.

## Limitations

Declared memory modes: full. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/task/step/steps/qc_metrics.py` (`QcMetricsStep`).
