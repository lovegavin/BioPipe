# SmiReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/smi_reader.py`](../../../src/reader/readers/smi_reader.py)
- Extensions: `.smi`
- Compression handled natively: `False`
- Tests: [`tests/test_extension10.py`](../../../tests/test_extension10.py)

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
SMILES .smi reader with length and approximate heavy-atom count.
```

### Module documentation

```text
SMILES line reader.

The heavy-atom count is a simple token approximation, not a full
chemical formula parser; it is documented rather than hidden.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/SmiReader.md` and regenerate.
