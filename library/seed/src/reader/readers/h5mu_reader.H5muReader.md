<!-- operon:generated -->
# MuData multimodal HDF5 reader

## Purpose

> MuData (``.h5mu``) reader.
>
> MuData stores one or more modalities under ``/mod/<name>``. Each modality
> carries its own ``X`` matrix plus ``obs``/``var`` groups whose ``_index``
> datasets hold the sample and feature names. ``X`` may be a dense HDF5
> dataset or a sparse CSR group (``data``/``indices``/``indptr``/``shape``).
>
> The reader returns a dense ``Form`` for one modality. When the file holds
> several modalities, ``modality`` selects one; a single-modality file is
> read without it.

## Inputs and outputs

Kind: `reader`. Operator ID: `H5muReader`.
This Reader opens files with extensions: `.h5mu`.
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

Implementation: `src/reader/readers/h5mu_reader.py` (`H5muReader`).
