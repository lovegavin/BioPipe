<!-- operon:generated -->
# pseudotime_dpt

## Purpose

> Diffusion pseudotime over a low-dimensional embedding.
>
> Input: 2D numeric Form [cell, component] (for example PCA scores).
> Output: 2D Form [cell, pseudotime] with one column in [0, 1].
>
> The implementation builds an adaptive Gaussian kNN graph, symmetrises it and
> uses the leading diffusion components of the random-walk matrix, weighted by
> lambda / (1 - lambda) as in Haghverdi et al. (2016), Eq. 15. Pseudotime is the
> Euclidean distance to the root cell in that diffusion space, normalised by its
> maximum.
>
> Diffusion pseudotime from a cell-by-component embedding.

## Inputs and outputs

Kind: `operator`. Operator ID: `pseudotime_dpt`.
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

Implementation: `src/task/step/steps/pseudotime_dpt.py` (`PseudotimeDptStep`).
