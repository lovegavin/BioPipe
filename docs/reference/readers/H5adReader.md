# H5adReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/h5ad_reader.py`](../../../src/reader/readers/h5ad_reader.py)
- Extensions: `.h5ad`
- Compression handled natively: `False`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py), [`tests/test_audit_fixes.py`](../../../tests/test_audit_fixes.py), [`tests/test_packages.py`](../../../tests/test_packages.py)

## File input hints

```json
{
  "dims": [
    "sample",
    "feature"
  ],
  "labels": {
    "sample": "builtin",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `layer` | Layer | string / null |  |  |

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
Reader for .h5ad files.
```

### Module documentation

```text
H5AD reader (AnnData).

Reads the main expression matrix and its two axes' identifiers from
an .h5ad file.

Layout:
    axis 0 = obs (cells), axis 1 = var (genes).

The matrix is read from ``adata.X`` unless ``args.layer`` names a
layer, in which case ``adata.layers[<name>]`` is used. Sparse
matrices are densified.

Cell and gene identifiers come from ``adata.obs.index`` and
``adata.var.index``.

H5AD internal compression is handled by h5py. External .gz/.bz2/.xz
wrappers are decompressed to a temporary disk file by the framework.

Label rules accepted:

    builtin           cell: obs.index
                      gene: var.index
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Reference
---------
AnnData: https://anndata.readthedocs.io/

Info fields set:

    missing_code      np.nan
```

## Curated notes

## 审校补充（H5AD）

- 读 `adata.X`；`layer` 指定时读 `adata.layers[layer]`。
- 稀疏矩阵会被 densify；超大 H5AD 先确认内存预算，或使用支持 disk 的路径。
- 标签来自 `obs.index`/`var.index`；重复标签会加 `#position`。
- 外部 `.gz/.bz2/.xz` 由 framework 解压；H5AD 内部压缩由 h5py 处理。
- 不要假设 `X` 已归一化/对数化；在 ANALYSIS 写明 layer 和预处理状态。
