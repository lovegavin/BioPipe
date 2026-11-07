<!-- operon:generated -->
# Alpha diversity

## Purpose

> Diversity metrics along one axis of a form.
>
> Reduce ``dim`` into one or more diversity metrics, preserving every other
> axis. The output replaces the reduced axis with a final ``metric`` axis.
>
> Metrics
> -------
>     shannon        Shannon entropy H = -sum(p_i * log(p_i))
>     simpson        Gini-Simpson index 1 - sum(p_i^2)
>     richness       number of non-zero values
>     evenness       Shannon / log(richness)
>     gini           Gini coefficient of the distribution
>
> Where p_i = v_i / sum(v) is the relative abundance of the i-th
> position along the other axis. Non-finite values are dropped before
> computing p; a position whose total is zero yields NaN for every
> metric that requires proportions.
>
> Axis-parallel info on the reduced dim is dropped from the output.
> Info for surviving dims passes through. ``info["encoders"]`` is
> trimmed to surviving dims.
>
> Params:
>     dim      : dimension to compute metrics along (required)
>     metrics  : metric name, or list of names (required)
>     output   : context key for the result (default: step name)
>
> Compute diversity metrics along one axis.

## Inputs and outputs

Kind: `operator`. Operator ID: `diversity`.
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

Implementation: `src/task/step/steps/diversity.py` (`DiversityStep`).
