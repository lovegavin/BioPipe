<!-- operon:generated -->
# kmer_count

## Purpose

> k-mer counts per sequence for any sequence-codes Form.
>
> Input: any Form declaring info["representation"] == "sequence_codes"
> with info["alphabet"] in {"dna","rna"}. The character-to-code mapping
> comes from info["alphabet_map"], so the operator works with any reader
> declaring the same convention.
>
> Output:
>     data   2D float32, shape (n_kmers, n_sequences)
>     dims   [kmer, sequence]
>     labels kmer = every A/C/G/T word of length k, in lexicographic order
>            sequence = the input's sequence labels
>
> Only fully A/C/G/T windows are counted. Windows containing N or any
> other code are skipped. Different sequence lengths are handled by the
> input's NaN padding; windows that would extend past the last defined
> position are skipped.
>
> Params:
>     sequence_dim : name of the sequence axis (default "sequence")
>     position_dim : name of the position axis (default "position")
>     k            : word length, 1..6 (default 3)
>     output       : context key for the result (default: step name)
>
> Count k-mers per sequence for any sequence-codes Form.

## Inputs and outputs

Kind: `operator`. Operator ID: `kmer_count`.
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

Implementation: `src/task/step/steps/kmer_count.py` (`KmerCountStep`).
