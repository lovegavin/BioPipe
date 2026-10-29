# GctReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/gct_reader.py`](../../../src/reader/readers/gct_reader.py)
- Extensions: `.gct`
- Compression handled natively: `False`
- Tests: [`tests/test_extension3.py`](../../../tests/test_extension3.py)

## File input hints

```json
{
  "dims": [
    "sample",
    "gene"
  ],
  "labels": {
    "sample": "builtin",
    "gene": "builtin"
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
Reader for .gct expression matrices; output is sample x gene.
```

### Module documentation

```text
GCT gene-expression reader (GCT 1.2 and 1.3).
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/GctReader.md` and regenerate.
