<!-- operon:generated -->
# scale_features

## Purpose

> Z-score standardisation along one axis of a 2D numeric Form.
>
> Input: any 2D Form. Missing cells are recognised from
> info["missing_code"]; when that code is NaN, non-finite cells count
> as missing. Missing cells stay missing in the output.
>
> For every position along the *other* axis, values are rescaled so
> that, across ``dim``, they have mean 0 and population standard
> deviation 1:
>
>     x' = (x - mean_over_dim) / std_over_dim
>
> Mean and std are computed with NaN-aware aggregation. Positions whose
> std is effectively zero are shifted to 0 (the numerator is already
> 0 for a constant row), not turned into NaN.
>
> When ``max_value`` is given, the rescaled value is clipped to
> [-max_value, +max_value] after standardisation.
>
> Output: same dims and labels as the input. ``data`` is replaced;
> ``representation`` becomes ``"scaled"``; genotype/alphabet semantics
> and encoders are cleared because the numeric values no longer mean
> what they meant.
>
> Params:
>     dim        : axis to standardise *along* (default "sample")
>                  e.g. dim="sample" scales each feature across samples
>                  dim="feature" scales each sample across features
>     max_value  : optional clip on the absolute standardised value
>     output     : context key (default: step name)

## Inputs and outputs

Kind: `operator`. Operator ID: `scale_features`.
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

Implementation: `src/task/step/steps/scale_features.py` (`ScaleFeaturesStep`).
