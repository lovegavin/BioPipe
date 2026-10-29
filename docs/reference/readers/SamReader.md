# SamReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/sam_reader.py`](../../../src/reader/readers/sam_reader.py)
- Extensions: `.sam`
- Compression handled natively: `False`
- Tests: [`tests/test_extension4.py`](../../../tests/test_extension4.py)

## File input hints

```json
{
  "dims": [
    "region",
    "field"
  ],
  "labels": {
    "region": "auto",
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
Sequence Alignment/Map text reader.
```

### Module documentation

```text
SAM text reader.

Reads the 11 mandatory SAM fields and skips @ header lines.
Binary BAM/CRAM files are not handled by this reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/SamReader.md` and regenerate.
