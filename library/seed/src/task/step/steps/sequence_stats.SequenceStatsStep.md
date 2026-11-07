<!-- operon:generated -->
# sequence_stats

## Purpose

> Per-sequence summary statistics for sequence-codes forms.
>
> Input: any Form declaring info["representation"] == "sequence_codes".
> The character-to-code mapping is read from info["alphabet_map"], so
> the operator works with any reader that declares the same convention
> (FASTA today; FASTQ, 2bit, GenBank, ... later).
>
> Output: [sequence, statistic] float32 with
>     length       number of non-padding positions
>     gc           (C + G) / length
>     n_ratio      N / length
>     valid_ratio  length / max_position
>
> Only DNA/RNA alphabets (info["alphabet"] in {"dna","rna"}) are accepted;
> GC content is undefined for protein.
>
> Params:
>     sequence_dim : name of the sequence axis (default "sequence")
>     position_dim : name of the position axis (default "position")
>     output       : context key for the result (default: step name)
>
> Per-sequence length, GC and N content for any sequence-codes Form.

## Inputs and outputs

Kind: `operator`. Operator ID: `sequence_stats`.
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

Implementation: `src/task/step/steps/sequence_stats.py` (`SequenceStatsStep`).
