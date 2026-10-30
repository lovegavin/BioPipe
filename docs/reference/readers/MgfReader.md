# MgfReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/mgf_reader.py`](../../../src/reader/readers/mgf_reader.py)
- Extensions: `.mgf`
- Compression handled natively: `True`
- Tests: [`tests/test_extension11.py`](../../../tests/test_extension11.py)

## File input hints

```json
{
  "dims": [
    "spectrum",
    "feature"
  ],
  "labels": {
    "spectrum": "auto",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |
| `max_spectra` | Max Spectra | integer | 100000 |  |

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
MGF reader returning one row per spectrum (peak lists are summarized).
```

### Module documentation

```text
Mascot Generic Format (MGF) spectrum summary reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MgfReader.md` and regenerate.
