# ParquetReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/parquet_reader.py`](../../../src/reader/readers/parquet_reader.py)
- Extensions: `.parquet`
- Compression handled natively: `False`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py)

## File input hints

```json
{
  "dims": [
    "sample",
    "feature"
  ],
  "labels": {
    "sample": "auto",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |

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
Reader for .parquet files.
```

### Module documentation

```text
Parquet reader.

A two-dimensional columnar table. Column names come from the Parquet
metadata; there is no header-line concept and no ``header`` arg.

Parquet internal compression is handled by pyarrow. External compression
wrappers are decompressed to disk by the framework before parsing.

Label rules accepted:

    builtin           column names from Parquet metadata
    auto              position indices "0", "1", ...
    {<col_dim>: <k>}  read column <k>; its values become the row
                      labels and the column is removed from data
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto``. Duplicate labels are
disambiguated by appending ``#<position>``.

A Parquet file may carry an index. If it does, it is treated as the
first column.

Non-numeric columns are encoded. The encoder instance used for each
column is recorded in ``info["encoders"]`` as
``{col_dim: {label: encoder}}``.

Info fields set:

    missing_code      np.nan
    encoders          present only when a column was encoded
```

## Curated notes

## 审校补充（Parquet）

- 列名来自 Parquet metadata，没有 header 行；`header` 参数不存在。
- 文件自带 index 时作为第一列；需要区分 index 和普通列。
- 非数值列编码进 `info["encoders"]`；数值列保持原 dtype/精度。
- Parquet 内部压缩由 pyarrow 处理；外部 `.gz` 由 framework 解压。
- 读取是整表载入；超大 Parquet 先选列/行子集。
