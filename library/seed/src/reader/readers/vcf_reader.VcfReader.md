<!-- operon:generated -->
# VcfReader

## Purpose

> VCF reader.
>
> Parses the GT field into per-ALT allele counts. Multi-allelic records
> are split into one output row per ALT. Missing alleles become NaN.
>
> Backend selection
> -----------------
> On Linux/macOS this uses cyvcf2 (htslib), which is fast.
> On Windows, cyvcf2/htslib is experimental and crashes the interpreter
> with STATUS_HEAP_CORRUPTION (0xC0000374) on many real VCFs. There we
> fall back to a pure Python parser. Same input, same output.
>
> Layout
> ------
>     axis 0 = variant, axis 1 = sample.
>
> Variant ID policy
> -----------------
>     ID present, single ALT   use the ID as-is
>     ID present, multi ALT    ``{id}:{alt}`` per split row
>     ID missing               ``{CHROM}:{POS}:{ALT}`` per split row
>
> Info fields set
> ---------------
>     missing_code      ``np.nan``
>     ploidy            inferred from the first non-missing GT
>     chrom             ``list[str]``, length = number of variant rows
>     pos               ``list[int]``, length = number of variant rows
>
> Reader for .vcf and .vcf.gz files.

## Inputs and outputs

Kind: `reader`. Operator ID: `VcfReader`.
This Reader opens files with extensions: `.vcf`.
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

Implementation: `src/reader/readers/vcf_reader.py` (`VcfReader`).
