<!-- operon:generated -->
# Ligand pose RMSD

## Purpose

> Symmetry-aware RMSD between two ligand poses.
>
> The pose is superposed onto the reference with the Kabsch algorithm; when
> ``allow_symmetry`` is on, atoms with the same element are re-matched with the
> Hungarian assignment inside each element group and the superposition is repeated
> until the matching stops changing.
>
> Symmetry-corrected ligand pose RMSD with per-atom deviations.

## Inputs and outputs

Kind: `operator`. Operator ID: `structure_ligand_pose_rmsd`.
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

Implementation: `src/task/step/steps/structure_ligand_pose_rmsd.py` (`StructureLigandPoseRmsdStep`).
