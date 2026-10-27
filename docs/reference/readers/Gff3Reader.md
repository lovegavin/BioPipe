# Gff3Reader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/gff3_reader.py`](../../../src/reader/readers/gff3_reader.py)
- Extensions: `.gff, .gff3`
- Compression handled natively: `False`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py)

## File input hints

```json
{
  "dims": [
    "record",
    "field"
  ],
  "labels": {
    "record": "auto",
    "field": "builtin"
  }
}
```

## Parameters

| key | title | type | default | required |
|---|---|---|---|---|
| `encoders` | Encoders | object |  |  |

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
Reader for .gff and .gff3 files.
```

### Module documentation

```text
GFF3 (Generic Feature Format version 3) reader.

A 9-column tab-delimited text file. Lines starting with ``#`` are
skipped, and reading stops at an embedded ``##FASTA`` section. Column
names and record semantics are documented on
:class:`src.reader.readers._gff_base._GffLikeReader`.

Reference
---------
GFF3 specification:
https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md
```

## Curated notes

## 审校补充（GFF3）

- 9 列、1-based inclusive；`start/end` 与 BED 的 0-based half-open 不同。
- `##FASTA` 之后是序列，不是注释；Reader 在这里停止，避免把序列当记录。
- `attributes` 是分号键值对；`ID`/`Parent` 关系用于 gene/transcript/exon 层级。
- 注释行的 `#` 不是数据；`##sequence-region` 等指令要跳过。
- 大文件建议先按 chromosome/feature type 子集，避免下游全量聚类。
