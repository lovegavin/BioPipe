<!-- operon:generated -->
# 附加注释

## Purpose

> Attach axis-parallel info arrays from a source form onto a target.
>
> The source declares which info keys are parallel to which axis via
> ``axis_info``. This step reads those arrays, aligns them to the
> target axis by label, and stores the result as target info entries
> declared parallel to the target dim.
>
> Data is never modified.
>
> Attach source info arrays to a target dimension.
>
> Inputs:
>     target : form to attach onto
>     source : form whose info holds the arrays
>
> Params:
>     fields     : list of info keys to attach
>     target_dim : dimension of the target to align against
>     output     : context key for the result

## Inputs and outputs

Kind: `operator`. Operator ID: `attach_info`.
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

Implementation: `src/task/step/steps/attach_info.py` (`AttachInfoStep`).
