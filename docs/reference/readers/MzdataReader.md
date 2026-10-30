# MzdataReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/mzdata_reader.py`](../../../src/reader/readers/mzdata_reader.py)
- Extensions: `.mzdata`
- Compression handled natively: `False`
- Tests: [`tests/test_extension13_readers.py`](../../../tests/test_extension13_readers.py)

## File input hints

```json
{
  "dims": [
    "spectrum",
    "feature"
  ],
  "labels": {
    "spectrum": "auto",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |
| `max_spectra` | Max Spectra | integer | 100000 |  |

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
mzData 1.05 reader: one spectrum per row.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MzdataReader.md` and regenerate.
