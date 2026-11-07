<!-- operon:generated -->
# TMM normalization

## Purpose

> Trimmed mean of M-values (TMM) normalization.
>
> This is an independent Python implementation of the TMM method from
> edgeR. Counts are scaled by effective library sizes
>
>     effective_library_size = library_size * norm_factor
>
> and converted to counts per ``target_sum``. The implementation follows
> edgeR's reference-sample selection, trimmed log-ratio mean and optional
> inverse-variance weighting, but is not a wrapper around R.

## Inputs and outputs

Kind: `operator`. Operator ID: `tmm_normalize`.
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

Implementation: `src/task/step/steps/tmm_normalize.py` (`TmmNormalizeStep`).
