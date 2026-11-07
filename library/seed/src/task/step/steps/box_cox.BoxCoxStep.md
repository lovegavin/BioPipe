<!-- operon:generated -->
# Box-Cox transform

## Purpose

> Box-Cox power transformation with optional per-feature MLE.
>
> The transformation is ``(x^lambda - 1) / lambda`` for ``lambda != 0`` and
> ``log(x)`` for ``lambda == 0``.  Each feature can have its own lambda,
> estimated by maximising the profile likelihood (the same criterion used by
> R's ``MASS::boxcox``).
>
> Missing cells are preserved.  ``shift`` can be used to make a feature
> strictly positive before fitting; the shift is applied before the transform
> and recorded in ``info``.

## Inputs and outputs

Kind: `operator`. Operator ID: `box_cox`.
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

Implementation: `src/task/step/steps/box_cox.py` (`BoxCoxStep`).
