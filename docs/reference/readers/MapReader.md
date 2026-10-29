# MapReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/map_reader.py`](../../../src/reader/readers/map_reader.py)
- Extensions: `.map`
- Compression handled natively: `False`
- Tests: [`tests/test_extension3b.py`](../../../tests/test_extension3b.py)

## File input hints

```json
{
  "dims": [
    "variant",
    "field"
  ],
  "labels": {
    "variant": "auto",
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
Reader for the four-column PLINK .map format.
```

### Module documentation

```text
PLINK .map variant map reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/MapReader.md` and regenerate.
