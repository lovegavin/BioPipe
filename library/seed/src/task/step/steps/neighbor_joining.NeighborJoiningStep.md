<!-- operon:generated -->
# Neighbor joining tree

## Purpose

> Neighbor-joining tree from a pairwise distance matrix.
>
> The topology and branch lengths follow the Saitou-Nei neighbor-joining
> algorithm: at each step the pair minimizing
> ``(m - 2) * d(i, j) - r(i) - r(j)`` is joined, with limb lengths
> ``d(i, j) / 2 + (r(i) - r(j)) / (2 * (m - 2))`` and ``d(i, j) - limb``.
> The final two clusters are attached to a synthetic root with half of
> their remaining distance.
>
> The result is a ``node x field`` table in the same encoding used by the
> Newick reader (parent / branch_length / depth / is_leaf), so it can be
> consumed by the tree operators such as patristic distance.

## Inputs and outputs

Kind: `operator`. Operator ID: `neighbor_joining`.
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

Implementation: `src/task/step/steps/neighbor_joining.py` (`NeighborJoiningStep`).
