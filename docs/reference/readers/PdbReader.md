# PdbReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/pdb_reader.py`](../../../src/reader/readers/pdb_reader.py)
- Extensions: `.pdb, .ent`
- Compression handled natively: `False`
- Tests: [`tests/test_extension8.py`](../../../tests/test_extension8.py)

## File input hints

```json
{
  "dims": [
    "atom",
    "field"
  ],
  "labels": {
    "atom": "auto",
    "field": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `model` | Model | integer | 0 |  |
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
ATOM/HETATM coordinate reader using fixed PDB columns.
```

### Module documentation

```text
Protein Data Bank (PDB) coordinate reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/PdbReader.md` and regenerate.
