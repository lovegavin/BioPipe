# MzidentmlReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/mzidentml_reader.py`](../../../src/reader/readers/mzidentml_reader.py)
- Extensions: `.mzid, .mzidentml`
- Compression handled natively: `False`
- Tests: [`tests/test_extension13_readers.py`](../../../tests/test_extension13_readers.py)

## File input hints

```json
{
  "dims": [
    "psm",
    "feature"
  ],
  "labels": {
    "psm": "auto",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |
| `max_psms` | Max Psms | integer | 1000000 |  |

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
mzIdentML 1.1/1.2 reader: one PSM per SpectrumIdentificationItem.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MzidentmlReader.md` and regenerate.
