# SdfReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/sdf_reader.py`](../../../src/reader/readers/sdf_reader.py)
- Extensions: `.sdf`
- Compression handled natively: `False`
- Tests: [`tests/test_extension9.py`](../../../tests/test_extension9.py)

## File input hints

```json
{
  "dims": [
    "molecule",
    "field"
  ],
  "labels": {
    "molecule": "auto",
    "field": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `max_records` | Max Records | integer | 10000 |  |
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
Reader for SDF records; output is molecule x [atoms, bonds, molecular_weight].
```

### Module documentation

```text
SDF molecular record summary reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/SdfReader.md` and regenerate.
