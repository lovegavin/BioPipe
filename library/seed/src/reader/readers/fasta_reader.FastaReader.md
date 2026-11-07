<!-- operon:generated -->
# FastaReader

## Purpose

> FASTA reader.
>
> Parses nucleotide or protein sequences.
>
> Layout:
>     axis 0 = sequence, axis 1 = position.
>
> Sequences of different lengths are padded with NaN to the maximum
> length found in the file. Characters are encoded as integers. For
> nucleotide input the legacy code table is used:
>
>     A=0, C=1, G=2, T=3, U=3, N=4, anything else=5
>
> When the alphabet is ``protein`` the twenty standard residues plus
> ``*`` use the code table shared with the sequence operators
> (``ACDEFGHIKLMNPQRSTVWY*`` -> 0..20) and every other residue
> (``B``, ``X``, ``Z``, ``J``, ...) is stored as ``unknown_code`` 21
> instead of the nucleotide code 5.
>
> Compression is handled by the framework; this reader sees plain
> files only.
>
> Label rules accepted:
>
>     builtin           sequence: first token after '>'
>     auto              position indices "0", "1", ...
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``auto`` for position and
> ``builtin`` for sequence. Duplicate identifiers are disambiguated by
> appending ``#<position>``.
>
> Sequence identifiers remain string axis labels; they are not data encoders.
>
> The alphabet is inferred from the observed characters and recorded
> in ``info["alphabet"]`` as one of ``"dna"``, ``"rna"`` or
> ``"protein"``. Pass ``alphabet`` (``auto``/``dna``/``rna``/``protein``)
> to override the inference.
>
> Reference
> ---------
> FASTA format:
> https://en.wikipedia.org/wiki/FASTA_format
>
> Info fields set:
>
>     missing_code      np.nan
>     alphabet          "dna" | "rna" | "protein"
>     alphabet_map      character -> integer code
>     unknown_code      integer code used for unlisted characters
>
> Reader for .fasta / .fa / .fna / .faa files.

## Inputs and outputs

Kind: `reader`. Operator ID: `FastaReader`.
This Reader opens files with extensions: `.fasta`, `.fa`, `.fna`, `.faa`.
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

Implementation: `src/reader/readers/fasta_reader.py` (`FastaReader`).
