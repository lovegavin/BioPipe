# ChainReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/chain_reader.py`](../../../src/reader/readers/chain_reader.py)
- Extensions: `.chain`
- Compression handled natively: `False`
- Tests: [`tests/test_extension5.py`](../../../tests/test_extension5.py)

## File input hints

```json
{
  "dims": [
    "alignment",
    "field"
  ],
  "labels": {
    "alignment": "auto",
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
UCSC chain alignment reader.
```

### Module documentation

```text
UCSC chain format reader.

Each header line describes one alignment block. Only header lines are
returned; the variable-length alignment data rows are skipped. Output is
alignment x field with a fixed twelve-column schema.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/ChainReader.md` and regenerate.
