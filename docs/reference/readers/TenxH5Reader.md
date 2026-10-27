# TenxH5Reader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/tenx_h5_reader.py`](../../../src/reader/readers/tenx_h5_reader.py)
- Extensions: `.h5`
- Compression handled natively: `False`
- Tests: none found

## File input hints

```json
{
  "dims": [
    "feature",
    "cell"
  ],
  "labels": {
    "feature": "builtin",
    "cell": "builtin"
  },
  "compression": [],
  "companions": []
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `feature_type` | 特征类型 | string |  |  |
| `feature_id_field` | 特征标识 | string; enum=['name', 'id'] | name |  |

## Output contract

```json
{
  "version": 1,
  "numeric": true,
  "info": {
    "missing_code": {
      "type": [
        "number",
        "null"
      ]
    },
    "encoders": {
      "type": "object",
      "optional": true
    },
    "representation": {
      "type": "string",
      "const": "counts"
    },
    "feature_types": {
      "type": "array",
      "items": "string"
    },
    "genome": {
      "type": "array",
      "items": "string"
    }
  },
  "dims": [],
  "labels": [],
  "parallel": [],
  "ndim": 2,
  "axis_fields": [],
  "info_open": false
}
```

## Processing rules (source docstring)

```text
Reader for 10x Cell Ranger h5 count matrices.
```

### Module documentation

```text
10x Genomics Cell Ranger HDF5 count matrix reader.

Reads ``filtered_feature_bc_matrix.h5`` (also
``raw_feature_bc_matrix.h5``) produced by Cell Ranger 3.0+. The
file is an HDF5 container with a sparse CSC feature x cell count
matrix and per-feature metadata (name, id, feature_type, genome).

Layout:
    axis 0 = feature
    axis 1 = cell

The ``filtered_feature_bc_matrix.h5`` from a CITE-seq experiment
holds both gene expression features and antibody capture features.
Read the two separately with ``feature_type``:

    feature_type: "Gene Expression"    -> genes x cells
    feature_type: "Antibody Capture"   -> antibodies x cells

Omitting ``feature_type`` returns every feature in a single matrix.

Label rules accepted:

    builtin           feature: gene symbol or antibody name
                                (or Ensembl id / antibody id with
                                ``feature_id_field='id'``)
                      cell:    10x barcode
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Info fields set:

    missing_code      np.nan
    representation    "counts"
    feature_types     per-feature Cell Ranger feature_type string
    genome            per-feature genome name ("" when absent)

``feature_types`` and ``genome`` are declared axis-parallel to the
feature axis in ``axis_info``.
```

## Curated notes

## 审校补充（10x H5）

- Cell Ranger 3.0+ 的 `filtered_feature_bc_matrix.h5`/`raw_feature_bc_matrix.h5`。
- CSC 矩阵，feature × cell；`feature_type` 可分离 `Gene Expression` 与 `Antibody Capture`。
- 省略 `feature_type` 会保留所有 feature；CITE-seq 通常要分别读取。
- 重复 feature 名会加 `#position`；`feature_id_field` 可用 Ensembl/antibody id。
- `feature_types`/`genome` 在 `axis_info[feature]`；不要把它们当 data 列。
