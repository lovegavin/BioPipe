# EmblReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/embl_reader.py`](../../../src/reader/readers/embl_reader.py)
- Extensions: `.embl`
- Compression handled natively: `False`
- Tests: [`tests/test_extension10.py`](../../../tests/test_extension10.py)

## File input hints

```json
{
  "dims": [
    "record",
    "field"
  ],
  "labels": {
    "record": "auto",
    "field": "builtin"
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
EMBL flat-file reader.
```

### Module documentation

```text
EMBL flat-file sequence reader.

Each record becomes one row with id, accession, description, organism,
sequence length, GC fraction and feature count. Sequence letters are
not retained.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/EmblReader.md` and regenerate.
