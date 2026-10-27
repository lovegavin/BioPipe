# TsvReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/tsv_reader.py`](../../../src/reader/readers/tsv_reader.py)
- Extensions: `.tsv`
- Compression handled natively: `True`
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
  },
  "compression": [
    ".gz",
    ".bz2",
    ".xz"
  ]
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `header` | Header row | boolean | True |  |
| `sep` | Separator | string |  |  |
| `encoders` | Encoders | object |  |  |
| `columns` | Columns | array |  |  |
| `info_columns` | Info columns | object |  |  |

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
Reader for .tsv files.
```

### Module documentation

```text
TSV reader.

Tab-separated two-dimensional tables. This is the CSV reader with a tab
default separator and the ``.tsv`` extension, so ``header``, ``sep``,
``columns``, ``info_columns``, ``encoders`` and all label rules behave
exactly as documented for :class:`CsvReader`.
```

## Curated notes

## 审校补充（TSV）

- 默认制表符分隔，其余行为与 CsvReader 一致（header/columns/encoders/缺失）。
- 不要用逗号分隔的 `.tsv` 而不指定 `sep`；Reader 不会自动猜。
- 非数值列编码；下游按标签对齐。
- `.tsv.gz/.bz2/.xz` 由 framework 解压。
