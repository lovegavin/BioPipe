<!-- operon:generated -->
# Moran's I

## Purpose

> Moran's I spatial autocorrelation.
>
> ``observed``, ``expected``, the normality standard deviation and the
> two-sided p-value follow ``ape::Moran.I``: weights are divided by their
> row sums, ``I = (n / S0) * (y' W y) / (y' y)`` and the variance uses the
> S1/S2 sums and the sample kurtosis.
>
> Moran's I for one value column and one distance matrix.

## Inputs and outputs

Kind: `operator`. Operator ID: `moran`.
Input count: `2`.
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

Implementation: `src/task/step/steps/moran.py` (`MoranStep`).
