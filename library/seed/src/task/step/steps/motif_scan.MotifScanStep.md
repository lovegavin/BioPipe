<!-- operon:generated -->
# motif_scan

## Purpose

> Scan IUPAC motifs across any sequence-codes Form.
>
> Input: any Form declaring info["representation"] == "sequence_codes"
> with info["alphabet"] in {"dna","rna"}.
>
> Motifs come in as {"name": "IUPAC-pattern"} and are matched on the
> forward strand. Each window of the same length is compared using the
> IUPAC convention:
>
>     A C G T U -> single base
>     R = A|G    Y = C|T    S = G|C    W = A|T
>     K = G|T    M = A|C    B = C|G|T  D = A|G|T
>     H = A|C|T  V = A|C|G  N = any
>
> Output:
>     data   2D float32, shape (n_motifs, n_sequences)
>     dims   [motif, sequence]
>     labels motif = user-supplied names, in insertion order
>            sequence = input sequence labels
>
> Counts include overlapping occurrences. Windows crossing N, unknown
> codes or the NaN padding are skipped.
>
> Params:
>     sequence_dim : name of the sequence axis (default "sequence")
>     position_dim : name of the position axis (default "position")
>     motifs       : {"name": "IUPAC-string"} mapping (required)
>     output       : context key for the result (default: step name)
>
> Count IUPAC motif occurrences per sequence.

## Inputs and outputs

Kind: `operator`. Operator ID: `motif_scan`.
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

Implementation: `src/task/step/steps/motif_scan.py` (`MotifScanStep`).
