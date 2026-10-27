# Plink1Reader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/plink_reader.py`](../../../src/reader/readers/plink_reader.py)
- Extensions: `.bed`
- Compression handled natively: `True`
- Tests: [`tests/test_assets.py`](../../../tests/test_assets.py)

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
    },
    "representation": {
      "type": "string",
      "const": "hard_call"
    },
    "ploidy": {
      "type": "integer",
      "min": 1,
      "const": 2
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
Reader for PLINK 1.x .bed / .bim / .fam triplets.
```

### Module documentation

```text
PLINK readers: 1.x (.bed/.bim/.fam) and 2.x (.pgen/.pvar/.psam).

Both readers produce the same layout:

    axis 0 = variant, axis 1 = sample.

PLINK 1.x
---------
    .bed    binary genotype matrix, variant-major (mode byte 0x01)
    .bim    variant metadata: CHROM ID CM POS A1 A2
    .fam    sample metadata:  FID IID PID MID SEX PHENO

PLINK 2.x
---------
    .pgen   binary genotype matrix
    .pvar   variant metadata (VCF-style or BIM-style header)
    .psam   sample metadata (header starts with #FID or #IID)

Routing
-------
A .bed is claimed by Plink1Reader only when .bim and .fam siblings
exist. Otherwise it is claimed by BedReader.
A .pgen is claimed by Plink2Reader only when .pvar and .psam siblings
exist.

Both readers declare ``handles_compression = True`` because their
sibling files must stay next to the target; the framework cannot
decompress to a temporary directory without breaking the sibling
lookups.

Variant ID policy
-----------------
    ID present, single ALT   use the ID as-is
    ID present, multi ALT    ``{id}:{alt}`` per split row
    ID missing               ``{CHROM}:{POS}:{ALT}`` per row
                             (PLINK 1.x uses A1 in place of ALT)

Label rules accepted
--------------------
    builtin           variant: ID column
                      sample:  IID column
    auto              position indices ``"0"``, ``"1"``, ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Info fields set
---------------
    missing_code      ``np.nan``
    ploidy            ``2``
    chrom             ``list[str]``, length = number of variant rows
    pos               ``list[int]``, length = number of variant rows

The ``chrom`` and ``pos`` arrays are parallel to the variant axis and
are kept in sync when the axis is subset (see ``Form.subset_axis``).
```

## Curated notes

## 审校补充（PLINK 1.x）

- 只有 `.bed` + `.bim` + `.fam` 同时存在时才由 Plink1Reader 认领；否则 `.bed` 走 BedReader。
- 输出 variant × sample 的硬调用（0/1/2），缺失为 NaN；不是 dosage。
- 多等位位点按 ALT 拆分；variant 标签规则见页面。
- 三个文件不能压缩；Reader 需要 sibling 留在原目录。
- 做 MAF/HWE/LD 前先确认样本/变异缺失率和 ploidy。
