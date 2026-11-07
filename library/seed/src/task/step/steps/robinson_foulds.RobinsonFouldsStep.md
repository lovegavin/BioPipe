<!-- operon:generated -->
# Robinson-Foulds distance

## Purpose

> Unweighted Robinson-Foulds distance between two trees.
>
> Both inputs use the node x field encoding produced by the tree readers
> (parent / branch_length / depth / is_leaf). The operator rebuilds each
> topology with ``load_tree``, extracts the nontrivial bipartitions
> (splits), canonically represents each split by its smaller side, and
> reports the symmetric difference:
>
>     rf            |splits(A) XOR splits(B)|
>     max_rf        |splits(A)| + |splits(B)|
>     normalized    rf / max_rf (0 when both trees have no nontrivial split)
>
> The statistics match ``dendropy.calculate.treecompare.
> unweighted_robinson_foulds_distance`` for unrooted topologies, with
> trivial splits (size 1 and n - 1) excluded.

## Inputs and outputs

Kind: `operator`. Operator ID: `robinson_foulds`.
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

Implementation: `src/task/step/steps/robinson_foulds.py` (`RobinsonFouldsStep`).
