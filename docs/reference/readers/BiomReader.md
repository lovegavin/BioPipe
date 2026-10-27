# BiomReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/biom_reader.py`](../../../src/reader/readers/biom_reader.py)
- Extensions: `.biom`
- Compression handled natively: `False`
- Tests: [`tests/test_new_readers.py`](../../../tests/test_new_readers.py)

## File input hints

```json
{
  "dims": [
    "sample",
    "taxon"
  ],
  "labels": {
    "sample": "builtin",
    "taxon": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `taxonomy` | Taxonomy | boolean | False |  |

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
Reader for .biom tables (JSON or HDF5).
```

### Module documentation

```text
BIOM reader for microbiome tables.

Supports BIOM 2.x JSON and HDF5 files. BIOM stores observations
(taxa) as rows and samples as columns; the matrix is returned as
(sample, taxon) so it composes naturally with metadata tables. The
``taxon`` axis keeps observation IDs (and optionally taxonomy strings).

BIOM's biological table is sparse. It is densified here because Loom-
like sparse disk preparation is not yet advertised by this Reader.
For very large tables a future disk protocol should be added rather
than silently raising memory pressure.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/BiomReader.md` and regenerate.
