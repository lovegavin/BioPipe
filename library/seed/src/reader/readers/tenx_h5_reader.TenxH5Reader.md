<!-- operon:generated -->
# Reader for 10x Cell Ranger h5 count matrices

## Purpose

> 10x Genomics Cell Ranger HDF5 count matrix reader.
>
> Reads ``filtered_feature_bc_matrix.h5`` (also
> ``raw_feature_bc_matrix.h5``) produced by Cell Ranger 3.0+. The
> file is an HDF5 container with a sparse CSC feature x cell count
> matrix and per-feature metadata (name, id, feature_type, genome).
>
> Layout:
>     axis 0 = feature
>     axis 1 = cell
>
> The ``filtered_feature_bc_matrix.h5`` from a CITE-seq experiment
> holds both gene expression features and antibody capture features.
> Read the two separately with ``feature_type``:
>
>     feature_type: "Gene Expression"    -> genes x cells
>     feature_type: "Antibody Capture"   -> antibodies x cells
>
> Omitting ``feature_type`` returns every feature in a single matrix.
>
> Label rules accepted:
>
>     builtin           feature: gene symbol or antibody name
>                                 (or Ensembl id / antibody id with
>                                 ``feature_id_field='id'``)
>                       cell:    10x barcode
>     auto              position indices "0", "1", ...
>     {name: pos, ...}  explicit mapping
>
> A missing dim entry defaults to ``builtin``. Duplicate labels are
> disambiguated by appending ``#<position>``.
>
> Info fields set:
>
>     missing_code      np.nan
>     representation    "counts"
>     feature_types     per-feature Cell Ranger feature_type string
>     genome            per-feature genome name ("" when absent)
>
> ``feature_types`` and ``genome`` are declared axis-parallel to the
> feature axis in ``axis_info``.

## Inputs and outputs

Kind: `reader`. Operator ID: `TenxH5Reader`.
This Reader opens files with extensions: `.h5`.
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

Implementation: `src/reader/readers/tenx_h5_reader.py` (`TenxH5Reader`).
