# ClsReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/cls_reader.py`](../../../src/reader/readers/cls_reader.py)
- Extensions: `.cls`
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
Reader for GSEA .cls categorical phenotype files.

    The output is ``[sample, feature]`` with one encoded ``class`` column.
    Class names are stored in the label encoder, so ``group_values`` can
    recover them for differential-expression operators.
```

### Module documentation

```text
GSEA .cls phenotype reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/ClsReader.md` and regenerate.
