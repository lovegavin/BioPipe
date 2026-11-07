<!-- operon:generated -->
# Plink1Reader

## Purpose

> PLINK readers: 1.x (.bed/.bim/.fam) and 2.x (.pgen/.pvar/.psam).
>
> Both readers produce the same layout:
>
>     axis 0 = variant, axis 1 = sample.
>
> PLINK 1.x
> ---------
>     .bed    binary genotype matrix, variant-major (mode byte 0x01)
>     .bim    variant metadata: CHROM ID CM POS A1 A2
>     .fam    sample metadata:  FID IID PID MID SEX PHENO
>
> PLINK 2.x
> ---------
>     .pgen   binary genotype matrix
>     .pvar   variant metadata (VCF-style or BIM-style header)
>     .psam   sample metadata (header starts with #FID or #IID)
>
> Routing
> -------
> A .bed is claimed by Plink1Reader only when .bim and .fam siblings
> exist. Otherwise it is claimed by BedReader.
> A .pgen is claimed by Plink2Reader only when .pvar and .psam siblings
> exist.
>
> Both readers declare ``handles_compression = True`` because their
> sibling files must stay next to the target; the framework cannot
> decompress to a temporary directory without breaking the sibling
> lookups.
>
> Variant ID policy
> -----------------
>     ID present, single ALT   use the ID as-is
>     ID present, multi ALT    ``{id}:{alt}`` per split row
>     ID missing               ``{CHROM}:{POS}:{ALT}`` per row
>                              (PLINK 1.x uses A1 in place of ALT)
>
> Label rules accepted
> --------------------
>     builtin           variant: ID column
>                       sample:  IID column
>     auto              position indices ``"0"``, ``"1"``, ...
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``builtin``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> Info fields set
> ---------------
>     missing_code      ``np.nan``
>     ploidy            ``2``
>     chrom             ``list[str]``, length = number of variant rows
>     pos               ``list[int]``, length = number of variant rows
>
> The ``chrom`` and ``pos`` arrays are parallel to the variant axis and
> are kept in sync when the axis is subset (see ``Form.subset_axis``).
>
> Reader for PLINK 1.x .bed / .bim / .fam triplets.

## Inputs and outputs

Kind: `reader`. Operator ID: `Plink1Reader`.
This Reader opens files with extensions: `.bed`.
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

Implementation: `src/reader/readers/plink_reader.py` (`Plink1Reader`).
