# GafReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/gaf_reader.py`](../../../src/reader/readers/gaf_reader.py)
- Extensions: `.gaf`
- Compression handled natively: `True`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py)

## File input hints

```json
{
  "dims": [
    "annotation",
    "field"
  ],
  "labels": {
    "annotation": "auto",
    "field": "builtin"
  },
  "compression": [
    ".gz"
  ]
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
Reader for GO Annotation Files (.gaf).
```

### Module documentation

```text
GO Annotation File (GAF) reader.

Tab-separated, 17 fixed columns, comment lines start with ``!``.

    db                    1  source database
    db_object_id          2  database-specific identifier
    db_object_symbol      3  gene symbol
    qualifier             4  NOT / contributes_to / ...
    go_id                 5  GO term identifier
    db_reference          6  reference
    evidence_code         7  EXP / IDA / ...
    with_from             8  supporting identifiers
    aspect                9  P / F / C
    db_object_name       10  full name
    db_object_synonym    11  pipe-separated synonyms
    db_object_type       12  protein / gene / ...
    taxon                13  NCBI taxonomy id
    date                 14  annotation date
    assigned_by          15  assigning group
    annotation_extension 16  structured extension
    gene_product_form_id 17  isoform identifier

Reference:
    https://geneontology.org/docs/go-annotation-file-gaf-format-2.2/

Layout
------
    dims = [annotation, field]

    ``annotation`` is one row per GAF annotation line.
    ``field`` holds the 16 non-synonym column names above.

``db_object_synonym`` is a pipe-separated multi-valued column. It is
read verbatim into ``info["db_object_synonym"]`` and declared parallel
to the annotation axis. The column is removed from data so it can be
exploded downstream.

Label rules accepted:

    builtin           the standard column names above
    auto              position indices
    {<field_dim>: <k>}  read column <k> as annotation labels
    {name: pos, ...}  explicit mapping

Info fields set:

    missing_code         np.nan
    db_object_synonym    list of strings
    encoders             one encoder per non-numeric column
```

## Curated notes

## 审校补充（GAF）

- 17 列固定，`!` 开头为注释；`db_object_synonym` 是管道分隔多值，放在 `info` 而非 data。
- GO 注释是“基因-术语”对，不是表达矩阵；下游通常 `pivot`/`enrich_go`。
- 不要直接按行数当基因数；一个基因可有多行/多术语。
- 大 GAF 读取慢，先确认 taxon/aspect 过滤需求。
