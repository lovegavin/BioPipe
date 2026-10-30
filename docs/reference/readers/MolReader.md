# MolReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/mol_reader.py`](../../../src/reader/readers/mol_reader.py)
- Extensions: `.mol`
- Compression handled natively: `False`
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)

## File input hints

```json
{
  "dims": [
    "molecule",
    "feature"
  ],
  "labels": {
    "molecule": "auto",
    "feature": "builtin"
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
Read one MDL MOL V2000 file and summarize its atom/bond block.
```

### Module documentation

```text
MDL MOL/SDF V2000 molecule summary reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MolReader.md` and regenerate.
