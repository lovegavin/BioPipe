# GtfReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/gtf_reader.py`](../../../src/reader/readers/gtf_reader.py)
- Extensions: `.gtf`
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
Reader for .gtf files.
```

### Module documentation

```text
GTF (Gene Transfer Format) reader.

A 9-column tab-delimited text file. Lines starting with ``#`` are
skipped, and reading stops at an embedded ``##FASTA`` section. Column
names and record semantics are documented on
:class:`src.reader.readers._gff_base._GffLikeReader`.

Reference
---------
GTF specification:
https://www.ensembl.org/info/website/upload/gff.html
```

## Curated notes

## 审校补充（GTF）

- 9 列、1-based inclusive；属性是 `key "value";` 形式，不是 GFF3 的 `key=value`。
- `gene_id`/`transcript_id` 是层级关键；`feature` 列常为 gene/transcript/exon。
- 与 GFF3 共用读取基类，但属性解析不同；不要混用两种文件的属性假设。
- 坐标/链方向要保持原样；负链基因的区间仍是 start<end（1-based）。
