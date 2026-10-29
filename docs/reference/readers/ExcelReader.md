# ExcelReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/excel_reader.py`](../../../src/reader/readers/excel_reader.py)
- Extensions: `.xlsx, .xlsm`
- Compression handled natively: `False`
- Tests: [`tests/test_extension3.py`](../../../tests/test_extension3.py)

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
| `sheet` | Sheet | string / integer | 0 |  |
| `header` | Header | boolean | True |  |
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
Reader for .xlsx and .xlsm workbooks.
```

### Module documentation

```text
Excel workbook reader using pandas/openpyxl.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/ExcelReader.md` and regenerate.
