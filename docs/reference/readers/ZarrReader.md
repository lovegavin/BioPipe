# ZarrReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/zarr_reader.py`](../../../src/reader/readers/zarr_reader.py)
- Extensions: `.zarr`
- Compression handled natively: `False`
- Tests: [`tests/test_extension8.py`](../../../tests/test_extension8.py)

## File input hints

```json
{
  "dims": [
    "sample",
    "feature"
  ],
  "labels": {
    "sample": "auto",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `array` | Array | string |  |  |

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
Read a two-dimensional numeric Zarr array or group member.
```

### Module documentation

```text
Zarr array reader (2-D numeric arrays).
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/ZarrReader.md` and regenerate.
