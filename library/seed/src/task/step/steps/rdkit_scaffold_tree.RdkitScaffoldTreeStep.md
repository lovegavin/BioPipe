<!-- operon:generated -->
# Murcko scaffold tree

## Purpose

> Hierarchical Murcko scaffold tree for a molecule collection.
>
> Each molecule contributes one node per scaffold level. Level 1 is the Bemis-Murcko
> scaffold, level 2 the scaffold of that scaffold, and so on until the chain becomes
> cyclic with nothing to strip (``c1ccccc1`` keeps itself) or empty.

## Inputs and outputs

Kind: `operator`. Operator ID: `rdkit_scaffold_tree`.
Input count: `0`.
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

Implementation: `src/task/step/steps/rdkit_scaffold_tree.py` (`RdkitScaffoldTreeStep`).
