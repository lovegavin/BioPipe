# TxtReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/txt_reader.py`](../../../src/reader/readers/txt_reader.py)
- Extensions: `.txt, .tab`
- Compression handled natively: `False`
- Tests: [`tasks/peak_nearest_gene_demo/test_peak_nearest_gene_gtf.py`](../../../tasks/peak_nearest_gene_demo/test_peak_nearest_gene_gtf.py), [`tests/test_assets.py`](../../../tests/test_assets.py)

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
| `header` | Header row | boolean | True |  |
| `sep` | Separator | string |  |  |
| `encoders` | Encoders | object |  |  |
| `columns` | Columns | array |  |  |
| `info_columns` | Info columns | object |  |  |
| `reader` | Delegate reader | string | csv |  |

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
  "axis_fields": [],
  "info_open": true
}
```

## Processing rules (source docstring)

```text
Read generic text files by delegating to another reader.
```

### Module documentation

```text
Generic text reader that delegates to another reader.

Handles .txt and .tab extensions that have no dedicated reader.
Parsing is delegated to another registered reader, selected by name.

Params:
    reader : name of the reader to delegate to, matched against the
             class name with "Reader" stripped and lowercased.
             Examples: "csv" -> CsvReader, "bed" -> BedReader,
             "gtf" -> GtfReader. Default "csv".
    All other args are forwarded to the delegated reader.

When the delegate is CsvReader and ``sep`` is not given, a tab
separator is assumed for .txt and .tab files.
```

## Curated notes

## 审校补充（TXT）

- `.txt` 没有固定格式；TxtReader 委托 CSV/TSV 解析，必须显式给出 `sep` 或 `reader`。
- 制表符文本建议 `sep: "\t"`；逗号文本用 `reader: csv` + `sep: ","`。
- 不要在未检查分隔符的情况下直接读取；先用 `biopipe inspect --arg sep=...`。
- 坐标/数值精度由委托 Reader 决定。
