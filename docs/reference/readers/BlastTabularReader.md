# BlastTabularReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/blast_tabular_reader.py`](../../../src/reader/readers/blast_tabular_reader.py)
- Extensions: `.blast6, .b6, .blasttab`
- Compression handled natively: `False`
- Tests: [`tests/test_extension10.py`](../../../tests/test_extension10.py)

## File input hints

```json
{
  "dims": [
    "hit",
    "field"
  ],
  "labels": {
    "hit": "auto",
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
BLAST outfmt 6 reader.
```

### Module documentation

```text
BLAST tabular (outfmt 6) reader.

Reads the 12 standard BLAST columns. Additional outfmt 6 columns are
ignored; use a dedicated reader for custom column sets.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/BlastTabularReader.md` and regenerate.
