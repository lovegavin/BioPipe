# H5Reader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/h5_reader.py`](../../../src/reader/readers/h5_reader.py)
- Extensions: `.hdf5`
- Compression handled natively: `False`
- Tests: [`tests/test_extension3b.py`](../../../tests/test_extension3b.py)

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
| `dataset` | Dataset | string / null | None |  |
| `sample_dim` | 样本维度 | string | sample |  |
| `feature_dim` | 特征维度 | string | feature |  |

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
Read a 2D numeric dataset from an .hdf5 file.
```

### Module documentation

```text
Generic HDF5 2D dataset reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/H5Reader.md` and regenerate.
