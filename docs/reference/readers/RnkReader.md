# RnkReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/rnk_reader.py`](../../../src/reader/readers/rnk_reader.py)
- Extensions: `.rnk`
- Compression handled natively: `False`
- Tests: [`tests/test_extension73.py`](../../../tests/test_extension73.py)

## File input hints

```json
{
  "dims": [
    "gene",
    "feature"
  ],
  "labels": {
    "gene": "builtin",
    "feature": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `header` | Header row | boolean | False |  |
| `comment` | Comment prefix | string | # |  |
| `gene_column` | Gene column | integer | 0 |  |
| `score_column` | Score column | integer | 1 |  |
| `feature_label` | Score label | string | score |  |

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
Reader for GSEA .rnk ranked gene lists.

    The output is ``[gene, feature]`` with a single numeric ``score``
    feature. File order is preserved because rank order is meaningful for
    preranked GSEA.
```

### Module documentation

```text
GSEA .rnk ranked-list reader.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/RnkReader.md` and regenerate.
