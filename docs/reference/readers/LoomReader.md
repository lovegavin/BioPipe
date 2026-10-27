# LoomReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/loom_reader.py`](../../../src/reader/readers/loom_reader.py)
- Extensions: `.loom`
- Compression handled natively: `False`
- Tests: [`tests/test_new_readers.py`](../../../tests/test_new_readers.py)

## File input hints

```json
{
  "dims": [
    "gene",
    "cell"
  ],
  "labels": {
    "gene": "builtin",
    "cell": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `matrix` | Matrix | string | matrix |  |
| `row_ids` | Row Ids | string |  |  |
| `col_ids` | Col Ids | string |  |  |

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
Reader for .loom files.
```

### Module documentation

```text
Loom reader for single-cell matrices.

A Loom file is HDF5. The default matrix is ``/matrix`` with shape
(genes, cells); row identifiers live in ``/row_attrs/GeneIDs`` and
column identifiers in ``/col_attrs/CellID``. Common alternatives
(``Gene``/``GeneIDs`` and ``CellID``/``CellIDs``) are accepted.

The reader keeps the matrix dense (Loom matrices are normally dense)
and preserves the first-axis/second-axis order from the manifest.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/LoomReader.md` and regenerate.
