# MmcifReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/mmcif_reader.py`](../../../src/reader/readers/mmcif_reader.py)
- Extensions: `.cif, .mmcif`
- Compression handled natively: `False`
- Tests: [`tests/test_extension9.py`](../../../tests/test_extension9.py)

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
| `max_atoms` | Max Atoms | integer | 100000 |  |
| `model` | Model | integer |  |  |
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
Reader for mmCIF atom_site loops; output is atom x field.
```

### Module documentation

```text
Minimal mmCIF atom_site loop reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MmcifReader.md` and regenerate.
