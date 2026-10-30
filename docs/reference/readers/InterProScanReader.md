# InterProScanReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/interproscan_reader.py`](../../../src/reader/readers/interproscan_reader.py)
- Extensions: `.iprscan`
- Compression handled natively: `False`
- Tests: [`tests/test_extension10.py`](../../../tests/test_extension10.py)

## File input hints

```json
{
  "dims": [
    "match",
    "field"
  ],
  "labels": {
    "match": "auto",
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
InterProScan tabular output reader.
```

### Module documentation

```text
InterProScan TSV reader (15 standard columns).
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/InterProScanReader.md` and regenerate.
