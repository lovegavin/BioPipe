# BroadPeakReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/broadpeak_reader.py`](../../../src/reader/readers/broadpeak_reader.py)
- Extensions: `.broadpeak`
- Compression handled natively: `False`
- Tests: [`tests/test_extension9.py`](../../../tests/test_extension9.py)

## File input hints

```json
{
  "dims": [
    "region",
    "field"
  ],
  "labels": {
    "region": "auto",
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
Reader for broadPeak files; output is region x field.
```

### Module documentation

```text
9-column broadPeak reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/BroadPeakReader.md` and regenerate.
