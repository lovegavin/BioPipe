<!-- operon:generated -->
# fastq_adapter_scan

## Purpose

> Scan FASTQ reads for common sequencing adapters.
>
> Input: FileArtifact (format fastq/fq).
> Output: 2D Form [adapter, metric] with ``reads_with_adapter`` and
> ``fraction`` columns for each configured adapter.
>
> A read counts for an adapter when a prefix of the adapter (at least
> ``min_overlap`` bases) aligns to the read at any offset with at most
> ``max_mismatches`` substitutions.  Each read is counted at most once per
> adapter.
>
> Count reads containing Illumina, Nextera or custom adapter prefixes.

## Inputs and outputs

Kind: `operator`. Operator ID: `fastq_adapter_scan`.
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

Implementation: `src/task/step/steps/fastq_adapter_scan.py` (`FastqAdapterScanStep`).
