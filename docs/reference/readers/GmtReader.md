# GmtReader

> Auto-generated reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/gmt_reader.py`](../../../src/reader/readers/gmt_reader.py)
- Extensions: `.gmt`
- Compression handled natively: `False`
- Tests: [`tests/test_new_readers.py`](../../../tests/test_new_readers.py)

## File input hints

```json
{
  "dims": [
    "gene",
    "gene_set"
  ],
  "labels": {
    "gene": "builtin",
    "gene_set": "builtin"
  }
}
```

## Parameters

This Reader has no parameters.

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
Reader for .gmt gene-set files.
```

### Module documentation

```text
GMT gene-set reader.

A GMT file has one gene set per line::

    set_name<TAB>description<TAB>gene1<TAB>gene2 ...

The result is a binary gene x set matrix. Genes are ordered by first
appearance in the file; duplicate set names are rejected, while duplicate
genes inside one set are collapsed.

The reader deliberately does **not** perform enrichment. It only
preserves set membership so `ora` / `gsea` can apply their own
statistics and multiple-testing policy.
```

## Before using this Reader

Check coordinate basis, missing values, compression handling and sibling-file requirements in the source/tests. Add caveats to `docs/reference/notes/readers/GmtReader.md` and regenerate.
