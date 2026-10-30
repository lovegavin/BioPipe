# BamReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/bam_reader.py`](../../../src/reader/readers/bam_reader.py)
- Extensions: `.bam`
- Compression handled natively: `False`
- Tests: [`tests/test_extension7.py`](../../../tests/test_extension7.py)

## File input hints

```json
{
  "dims": [
    "read",
    "field"
  ],
  "labels": {
    "read": "auto",
    "field": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `max_records` | Max Records | integer | 100000 |  |
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
Binary Alignment/Map reader.
```

### Module documentation

```text
BAM alignment reader using pysam.

Output is one row per alignment and numeric alignment fields; read names
are kept as the row labels.  An index is not required for sequential reads.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/BamReader.md` and regenerate.
