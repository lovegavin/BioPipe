# GfaReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/gfa_reader.py`](../../../src/reader/readers/gfa_reader.py)
- Extensions: `.gfa`
- Compression handled natively: `False`
- Tests: [`tests/test_extension7.py`](../../../tests/test_extension7.py)

## File input hints

```json
{
  "dims": [
    "segment",
    "field"
  ],
  "labels": {
    "segment": "auto",
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
GFA segment reader; links and paths are ignored.
```

### Module documentation

```text
Graph Fragment Assembly (GFA 1.x) segment reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/GfaReader.md` and regenerate.
