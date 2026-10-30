# HapmapReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/hapmap_reader.py`](../../../src/reader/readers/hapmap_reader.py)
- Extensions: `.hapmap`
- Compression handled natively: `False`
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)

## File input hints

```json
{
  "dims": [
    "variant",
    "sample"
  ],
  "labels": {
    "variant": "auto",
    "sample": "auto"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `has_header` | Has Header | boolean | True |  |
| `id_column` | Id Column | integer | 0 |  |
| `first_sample_column` | First Sample Column | integer | 10 |  |
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
HapMap genotype table, returned as variant x sample dosage.
```

### Module documentation

```text
HapMap genotype table reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/HapmapReader.md` and regenerate.
