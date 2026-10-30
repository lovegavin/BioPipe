# MafReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/maf_reader.py`](../../../src/reader/readers/maf_reader.py)
- Extensions: `.maf`
- Compression handled natively: `False`
- Tests: [`tests/test_extension5.py`](../../../tests/test_extension5.py)

## File input hints

```json
{
  "dims": [
    "variant",
    "field"
  ],
  "labels": {
    "variant": "auto",
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
Mutation Annotation Format table reader.
```

### Module documentation

```text
Mutation Annotation Format (MAF) reader.

Reads the tab-separated MAF table used by TCGA/GDC. Comment and version
lines beginning with ``#`` are skipped; the first remaining line is the
header. All columns are retained and returned as variant x field.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MafReader.md` and regenerate.
