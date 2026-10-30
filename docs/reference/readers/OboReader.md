# OboReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/obo_reader.py`](../../../src/reader/readers/obo_reader.py)
- Extensions: `.obo`
- Compression handled natively: `False`
- Tests: [`tests/test_extension9.py`](../../../tests/test_extension9.py)

## File input hints

```json
{
  "dims": [
    "term",
    "field"
  ],
  "labels": {
    "term": "auto",
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
Reader for [Term] stanzas in OBO files; output is term x field.
```

### Module documentation

```text
Open Biomedical Ontologies (OBO) term reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/OboReader.md` and regenerate.
