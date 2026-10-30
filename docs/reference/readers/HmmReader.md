# HmmReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/hmm_reader.py`](../../../src/reader/readers/hmm_reader.py)
- Extensions: `.hmm`
- Compression handled natively: `False`
- Tests: [`tests/test_extension10.py`](../../../tests/test_extension10.py)

## File input hints

```json
{
  "dims": [
    "model",
    "field"
  ],
  "labels": {
    "model": "auto",
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
HMMER3 profile reader.
```

### Module documentation

```text
HMMER3 profile HMM reader.

Reads NAME/LENG/ALPH/NSEQ from each profile header; alignment columns
are not materialised.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/HmmReader.md` and regenerate.
