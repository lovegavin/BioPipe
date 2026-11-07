<!-- operon:generated -->
# find_orfs

## Purpose

> Find complete ORFs (ATG..stop) in any sequence-codes Form.
>
> Input: any Form declaring info["representation"] == "sequence_codes"
> with info["alphabet"] in {"dna","rna"}.
>
> Output:
>     data   2D float32, shape (n_orfs, 6)
>     dims   [orf, statistic]
>     statistic = [strand, frame, start, end, length_nt, length_aa]
>     info["sequence"] is axis-parallel to "orf", naming each ORF's
>         source sequence label.
>
> Both strands are scanned. Forward strand uses strand=+1; the reverse
> complement uses strand=-1. For each chain, frames 0,1,2 start the
> codon grid at that offset. From every ATG, the first in-frame stop
> (TAA/TAG/TGA) closes an ORF. start and end are 0-based positions on
> the chain that strand refers to; end is the last base of the stop
> codon, so length_nt == end - start + 1 and length_aa == length_nt/3 - 1.
>
> Params:
>     sequence_dim : name of the sequence axis (default "sequence")
>     position_dim : name of the position axis (default "position")
>     min_aa       : minimum amino-acid count (default 1)
>     output       : context key for the result (default: step name)
>
> Locate complete ATG..stop ORFs on both strands.

## Inputs and outputs

Kind: `operator`. Operator ID: `find_orfs`.
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

Implementation: `src/task/step/steps/find_orfs.py` (`FindOrfsStep`).
