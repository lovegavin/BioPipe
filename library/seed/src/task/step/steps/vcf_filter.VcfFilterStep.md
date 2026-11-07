<!-- operon:generated -->
# vcf_filter

## Purpose

> Filter a VCF/VCF.gz and write the retained records as a native VCF file.
>
> The output is a byte-preserving subset: header meta lines and each retained
> record are copied verbatim, so INFO/FORMAT fields, phasing and sample order
> are unchanged.  The filtered file is registered as a native result and also
> exposed as a FileArtifact so downstream operators can consume it directly.
>
> Filters are site-level by default; sample-level missingness is only evaluated
> when ``max_missing_rate < 1``.
>
> Quality/type/region filtering with a native filtered VCF output.

## Inputs and outputs

Kind: `operator`. Operator ID: `vcf_filter`.
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

Implementation: `src/task/step/steps/vcf_filter.py` (`VcfFilterStep`).
