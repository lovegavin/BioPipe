<!-- operon:generated -->
# ProteinMPNN noise robustness

## Purpose

> ProteinMPNN design robustness across backbone coordinate noise levels.
>
> Each replicate perturbs the atom coordinates with zero-mean Gaussian noise and
> redesigns the structure with the official ProteinMPNN runner, so the reported
> sequence recovery and model scores describe how sensitive a design task is to
> small backbone displacements rather than to sampling randomness.
>
> ProteinMPNN sequence recovery under increasing backbone noise.

## Inputs and outputs

Kind: `operator`. Operator ID: `proteinmpnn_noise_robustness`.
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

Implementation: `src/task/step/steps/proteinmpnn_noise_robustness.py` (`ProteinmpnnNoiseRobustnessStep`).
