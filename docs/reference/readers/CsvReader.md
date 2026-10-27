# CsvReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/csv_reader.py`](../../../src/reader/readers/csv_reader.py)
- Extensions: `.csv`
- Compression handled natively: `True`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py), [`tests/test_audit_fixes.py`](../../../tests/test_audit_fixes.py), [`tests/test_contracts.py`](../../../tests/test_contracts.py), [`tests/test_task_tools.py`](../../../tests/test_task_tools.py)

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
Reader for .csv files.
```

### Module documentation

```text
CSV reader.

Comma-separated (or custom-separator) two-dimensional tables. The
first line is treated as a header by default; set ``header: false``
in args to read every line as data.

Compression (.gz, .bz2, .xz) is handled by pandas directly; this
reader receives the original path.

Label rules accepted:

    builtin           header row (valid only for the column dim)
    auto              position indices "0", "1", ...
    {<col_dim>: <k>}  read column <k>; its values become the row
                      labels and the column is removed from data.
                      ``k`` is a position in the original file,
                      independent of ``columns``.
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto``. Duplicate labels are
disambiguated by appending ``#<position>``.

Column selection
----------------
``columns`` restricts the reader to a subset of header names, in the
order given. ``labels`` indices still refer to the original file.

Info columns
------------
``info_columns`` maps a header name to an info field name. The column
is read verbatim as strings into ``info[field]`` and declared parallel
to the row dimension in ``axis_info``. The column is removed from
data.

Non-numeric columns are encoded. The encoder instance used for each
column is recorded in ``info["encoders"]`` as
``{col_dim: {label: encoder}}``.

Info fields set:

    missing_code      np.nan
    encoders          present only when a column was encoded
    <info_columns>    one entry per declared info column
```

## Curated notes

## 审校补充（CSV）

- 默认逗号分隔；制表符文件必须显式 `sep: "\t"`，不要假设自动嗅探。
- `header: true` 时第一行是列名；`columns`/`info_columns` 可抽取/声明列；非数值列编码进 `info["encoders"]`。
- 缺失标记默认识别为 NaN；空字符串/`NA` 的处理由参数决定，需在 ANALYSIS 说明。
- `.csv.gz/.bz2/.xz` 由 framework 解压到临时文件；Reader 看到的是普通 CSV。
- `reader: csv` 是路由选择器，不是 Reader 参数；`--check` 会剥离它。
