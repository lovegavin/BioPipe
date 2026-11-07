# ProteinMPNN design

## Purpose

> ProteinMPNN sequence design through the official runner script.
>
> Design sequences for a PDB structure with ProteinMPNN.

## Inputs and outputs

Kind: `operator`. Operator ID: `proteinmpnn_design`.
Input count: `0`.
The numeric design-score Form remains available for downstream analysis.
Sequences and original headers are declared as design-axis metadata so
`subset_axis` keeps them aligned when selecting or reordering designs.

Original ProteinMPNN FASTA and a `scores.csv` table (design, sequence, score,
global_score, seq_recovery) are preserved under the task's artifact directory.
Add an `export_results` branch directly from this operator: `format: native`
exposes both files, `format: fasta` selects sequences and `format: csv` selects
scores. With an empty filename these same-task files are referenced without
another copy. Native FASTA preserves reference records and chain encoding from
the official tool. Further calculations can continue from the Form in parallel.

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
declared working set. Export adapter tests use synthetic tool outputs and do not
establish the biological quality of generated sequences.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/task/step/steps/proteinmpnn_design.py` (`ProteinMpnnDesignStep`).
