# GrpReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/grp_reader.py`](../../../src/reader/readers/grp_reader.py)
- Extensions: `.grp`
- Compression handled natively: `False`
- Tests: [`tests/test_extension73.py`](../../../tests/test_extension73.py)

## File input hints

```json
{
  "dims": [
    "sample",
    "feature"
  ],
  "labels": {
    "sample": "builtin",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |
| `feature_label` | Phenotype column label | string | class |  |

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
Reader for GSEA .grp phenotype group files.

    The layout is the same as CLS: counts, a ``#`` class-name line, then
    one class index per sample. Output is ``[sample, feature]`` with one
    encoded phenotype column.
```

### Module documentation

```text
GSEA .grp phenotype reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/GrpReader.md` and regenerate.
