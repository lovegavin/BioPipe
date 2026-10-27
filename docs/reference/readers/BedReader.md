# BedReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/bed_reader.py`](../../../src/reader/readers/bed_reader.py)
- Extensions: `.bed`
- Compression handled natively: `False`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py)

## File input hints

```json
{
  "dims": [
    "region",
    "field"
  ],
  "labels": {
    "region": "auto",
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
Reader for UCSC .bed files.
```

### Module documentation

```text
UCSC BED reader.

A whitespace-delimited text file with 3 to 12 columns per line. No
header. Column meaning is fixed by the BED specification:

    0  chrom         chromosome name
    1  chromStart    0-based start
    2  chromEnd      end (exclusive)
    3  name          feature name
    4  score         0-1000
    5  strand        '+' or '-'
    6  thickStart
    7  thickEnd
    8  itemRgb       R,G,B
    9  blockCount
    10 blockSizes    comma-separated
    11 blockStarts   comma-separated

``track`` and ``browser`` lines at the top are skipped.

Compression is handled by the framework; this reader sees plain
files only.

Label rules accepted:

    builtin           the standard BED column names above
    auto              position indices "0", "1", ...
    {<other_dim>: <k>}  read column <k> as the other dim's labels
                        (removed from data)
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``auto``. Duplicate labels are
disambiguated by appending ``#<position>``.

Non-numeric columns (chrom, name, strand, ...) are encoded. The
encoder instance used for each column is recorded in
``info["encoders"]``.

Reference
---------
UCSC BED format: https://genome.ucsc.edu/FAQ/FAQformat.html#format1
GA4GH BED v1.0 formalises the same layout.

Info fields set:

    missing_code      np.nan
    encoders          present only when a column was encoded
```

## Curated notes

## 审校补充（BED）

- 坐标是 **0-based、半开区间**：`chromStart` 含，`chromEnd` 不含；不要按 GFF/GTF 的 1-based inclusive 解释。
- 无表头；`track`/`browser` 行跳过；列数 3–12，缺列时按 BED 规范补空/默认，不要假设第 4 列一定是 name。
- 非数值列（chrom/name/strand 等）编码进 `info["encoders"]`；数值坐标保持精确。
- 若同目录存在 `.bim`/`.fam`，`.bed` 会优先被 `Plink1Reader` 认领；普通 BED 请确保没有 PLINK 兄弟文件，或用 `args.reader: bed` 明确指定。
- 坐标大于 2^24 时仍按整数/无损路径处理，避免 float32 丢精度。
