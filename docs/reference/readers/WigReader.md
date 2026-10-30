# WigReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/wig_reader.py`](../../../src/reader/readers/wig_reader.py)
- Extensions: `.wig`
- Compression handled natively: `False`
- Tests: [`tests/test_extension7.py`](../../../tests/test_extension7.py), [`tests/test_extension9.py`](../../../tests/test_extension9.py)

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
| `max_records` | Max Records | integer | 1000000 |  |
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
Reader for fixedStep and variableStep WIG tracks; output is region x field.
```

### Module documentation

```text
WIG fixedStep/variableStep signal track reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/WigReader.md` and regenerate.
