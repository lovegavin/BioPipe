<!-- operon:generated -->
# H5adReader

## Purpose

> H5AD reader (AnnData).
>
> Reads the main expression matrix and its two axes' identifiers from
> an .h5ad file.
>
> Layout:
>     axis 0 = obs (cells), axis 1 = var (genes).
>
> The matrix is read from ``adata.X`` unless ``args.layer`` names a
> layer, in which case ``adata.layers[<name>]`` is used. Sparse
> matrices are densified.
>
> Cell and gene identifiers come from ``adata.obs.index`` and
> ``adata.var.index``.
>
> H5AD internal compression is handled by h5py. External .gz/.bz2/.xz
> wrappers are decompressed to a temporary disk file by the framework.
>
> Label rules accepted:
>
>     builtin           cell: obs.index
>                       gene: var.index
>     auto              position indices "0", "1", ...
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``builtin``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> Reference
> ---------
> AnnData: https://anndata.readthedocs.io/
>
> Info fields set:
>
>     missing_code      np.nan
>
> Reader for .h5ad files.

## Inputs and outputs

Kind: `reader`. Operator ID: `H5adReader`.
This Reader opens files with extensions: `.h5ad`.
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

Declared memory modes: full, disk. Operon retains the existing planner, disk-backed
inputs and emergency spill behavior; full-mode operators still require their
declared working set. This generated reference has not been independently
scientifically reviewed.

## Examples

Use the registry to discover compatible Readers and validate a complete workflow
before execution. This generated page does not claim an executable scientific
example. Add a tested example and replace this generated page with authored
guidance when extending this operator.

## Source

Implementation: `src/reader/readers/h5ad_reader.py` (`H5adReader`).
