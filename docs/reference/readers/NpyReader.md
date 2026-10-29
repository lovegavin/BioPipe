# NpyReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/npy_reader.py`](../../../src/reader/readers/npy_reader.py)
- Extensions: `.npz`
- Compression handled natively: `False`
- Tests: [`tests/test_extension3.py`](../../../tests/test_extension3.py), [`tests/test_extension_guides.py`](../../../tests/test_extension_guides.py), [`tests/test_packages.py`](../../../tests/test_packages.py), [`tests/test_plugin_refresh.py`](../../../tests/test_plugin_refresh.py)

## File input hints

```json
{
  "dims": [
    "sample",
    "feature"
  ],
  "labels": {
    "sample": "auto",
    "feature": "auto"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `key` | Key | string |  |  |

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
Reader for 2D numeric .npy/.npz arrays; output is sample x feature.
```

### Module documentation

```text
NumPy array reader for .npy and .npz files.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/NpyReader.md` and regenerate.
