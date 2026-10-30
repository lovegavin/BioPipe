# CramReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/cram_reader.py`](../../../src/reader/readers/cram_reader.py)
- Extensions: `.cram`
- Compression handled natively: `False`
- Tests: none found

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
| `reference` | Reference | string |  |  |
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
Compressed Reference-oriented Alignment/Map reader.
```

### Module documentation

```text
CRAM alignment reader using pysam.

A reference FASTA must be supplied as ``reference`` because CRAM stores
alignments relative to a reference sequence.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/CramReader.md` and regenerate.
