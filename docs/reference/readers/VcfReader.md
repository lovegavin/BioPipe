# VcfReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/vcf_reader.py`](../../../src/reader/readers/vcf_reader.py)
- Extensions: `.vcf`
- Compression handled natively: `True`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py), [`tests/test_vcf_windows.py`](../../../tests/test_vcf_windows.py)

## File input hints

```json
{
  "dims": [
    "variant",
    "sample"
  ],
  "labels": {
    "variant": "builtin",
    "sample": "builtin"
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
    },
    "representation": {
      "type": "string",
      "const": "hard_call"
    },
    "ploidy": {
      "type": "integer",
      "min": 1
    },
    "chrom": {
      "type": "array",
      "items": "string"
    },
    "pos": {
      "type": "array",
      "items": "integer"
    }
  },
  "dims": [],
  "labels": [],
  "parallel": [],
  "ndim": 2,
  "values": "allele_count",
  "axis_fields": [
    {
      "axis": 0,
      "fields": [
        "chrom",
        "pos"
      ]
    }
  ],
  "info_open": false
}
```

## Processing rules (source docstring)

```text
Reader for .vcf and .vcf.gz files.
```

### Module documentation

```text
VCF reader.

Parses the GT field into per-ALT allele counts. Multi-allelic records
are split into one output row per ALT. Missing alleles become NaN.

Backend selection
-----------------
On Linux/macOS this uses cyvcf2 (htslib), which is fast.
On Windows, cyvcf2/htslib is experimental and crashes the interpreter
with STATUS_HEAP_CORRUPTION (0xC0000374) on many real VCFs. There we
fall back to a pure Python parser. Same input, same output.

Layout
------
    axis 0 = variant, axis 1 = sample.

Variant ID policy
-----------------
    ID present, single ALT   use the ID as-is
    ID present, multi ALT    ``{id}:{alt}`` per split row
    ID missing               ``{CHROM}:{POS}:{ALT}`` per split row

Info fields set
---------------
    missing_code      ``np.nan``
    ploidy            inferred from the first non-missing GT
    chrom             ``list[str]``, length = number of variant rows
    pos               ``list[int]``, length = number of variant rows
```

## Curated notes

## 审校补充（VCF）

- 默认硬调用基因型；多等位按 ALT 拆分，一行可能变多行。
- 缺失/半缺失（`0/.` 等）按 NaN；在 ANALYSIS 写明 ploidy/缺失比例。
- `reader='vcf'` 是路由选择器，不是 Reader 参数。
- 大 VCF 先子集/转 BGEN/PLINK；全量读取耗时和内存都高。
- POS 是 1-based；与 BED 做区间分析前先确认坐标基准。
