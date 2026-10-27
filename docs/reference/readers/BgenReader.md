# BgenReader

> Reviewed reference. Verify format edge cases against the linked source and tests.

- Source: [`src/reader/readers/bgen_reader.py`](../../../src/reader/readers/bgen_reader.py)
- Extensions: `.bgen`
- Compression handled natively: `False`
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
      "const": "dosage"
    },
    "ploidy": {
      "type": "integer",
      "min": 1,
      "const": 2
    }
  },
  "dims": [],
  "labels": [],
  "parallel": [],
  "ndim": 2,
  "values": "allele_count",
  "axis_fields": [],
  "info_open": false
}
```

## Processing rules (source docstring)

```text
Reader for biallelic diploid .bgen files.
```

### Module documentation

```text
BGEN reader for biallelic diploid files.

BGEN stores genotype probabilities P(AA), P(AB), P(BB) per variant
per sample. This reader computes the expected ALT allele dosage:

    dosage = P(AB) + 2 * P(BB)

Layout:
    axis 0 = variant, axis 1 = sample.

Scope
-----
This reader handles biallelic diploid BGEN files only.

Two common non-compliant cases raise an explicit ``ReaderError``
instead of silently producing wrong data:

* Non-diploid data (haplotypes, haploids) — the sum of the three
  genotype probabilities is not 2 for at least one variant.
* Complex data (per-variant allele count or ploidy variation) —
  ``bgen_reader`` cannot unify the genotypes into a single tensor,
  or the tensor does not have exactly 3 genotype columns per
  variant.

Label rules accepted:

    builtin           variant: ids from the BGEN
                      sample:  samples from the BGEN
    auto              position indices "0", "1", ...
    {name: pos, ...}  explicit mapping

A missing dim entry defaults to ``builtin``. Duplicate labels are
disambiguated by appending ``#<position>``.

Info fields set:

    missing_code      np.nan
    ploidy            2
    representation    "dosage"

Reference
---------
BGEN specification: https://www.well.ox.ac.uk/~gav/bgen_format/
```

## Curated notes

## 审校补充（BGEN）

- 只支持双等位、二倍体 BGEN；haplotype/haploid/complex 会明确报错。
- `data` 是 ALT 期望 dosage `P(AB)+2*P(BB)`，不是硬调用；全零概率行变 NaN。
- `info.chrom`/`info.pos` 来自 BGEN 元数据，并声明在 `axis_info[variant]`。
- 复杂/多等位 BGEN 先转 VCF，再用 VcfReader。
