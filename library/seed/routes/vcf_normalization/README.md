# VCF normalization and merging

Three-step route that normalizes a multi-sample VCF against its reference,
concatenates two shards of the same callset, and merges a sample into another
callset. The outputs stay plain VCF text so they can be diffed line by line
against `bcftools`.

## Inputs

All inputs are public 1000 Genomes phase 3 data for chromosome 22 (GRCh37),
plus the matching reference slice.

| Source | File | Bytes | SHA256 | Content |
| --- | --- | --- | --- | --- |
| subset | `subset.vcf.gz` | 620,963 | `f67e2332b39e6c51aa5dcf6f33f6929937207debe99e4c042418fe6ef9ca042e` | 30,104 records, 50 samples, 172 multi-allelic sites, 1,581 indels, FORMAT `GT` only |
| part_a | `partA.vcf.gz` | 273,934 | `a88b705bd1b3dd8678252cbf967698d780add2547490e63f98e25f142a815ed4` | first shard of `subset` |
| part_b | `partB.vcf.gz` | 350,336 | `26fcddd07bd2b2acb63c5af1ef4e3620aae04ec945ec2982e75f191f683501b3` | second shard of `subset` |
| truth_norm | `truth_norm.vcf.gz` | 30,944 | `3492060aa6272380403741dff1c4ea430745c4c1647940e0c695d847a0e9af5b` | GIAB HG001 calls normalized with `bcftools norm -m -any` (1 sample) |
| reference | `chr22_1000g.fa` | 52,330,662 | `51c376f6c0b898b23bc067f53d93ca801beabfb1d846898372837d37d5578829` | GRCh37 chr22, soft-masked |

`subset` and the two shards were produced from the 1000 Genomes chr22 release
with `bcftools view -s` and `bcftools view -r`; `truth_norm` is the GIAB HG001
truth set restricted to the same interval. The compressed VCFs keep their tabix
indexes next to them (`.tbi`), which the reader uses for random access.

## Steps

1. `vcf_normalize` (`subset` + `reference`): split multi-allelic records into
   biallelic ones, left-align and trim every allele with the vt algorithm,
   remap the `GT` field (`1/2` -> `1/0` and `0/1` on the split rows) and recount
   `AC`, `AF`, `AN` from the genotypes.
2. `vcf_concat` (`part_a` + `part_b`): append the shards in input order after
   checking that both carry identical sample lists.
3. `vcf_merge` (`normalized` + `truth_norm`): union of sites and samples, missing
   genotypes filled with `./.`, `FORMAT` keys unioned, and INFO `AC/AF/AN`
   recomputed over the merged sample set.

The route finishes with three `export_results` steps and writes
`normalized.vcf`, `concatenated.vcf` and `merged.vcf`.

## Result (WSL, one clean run)

`total_elapsed 2.5494 s` (normalize 0.465 s, concat 0.152 s, merge 1.932 s),
wall 3.4 s, max RSS about 530 MB.

| Artifact | Bytes | MD5 |
| --- | --- | --- |
| `normalized.vcf` | 10,414,937 | `70892ad908c889538f3255aa69f2c1bf` |
| `concatenated.vcf` | 10,350,619 | `70e71d4af57ff5e5e1e27d0265c0f767` |
| `merged.vcf` | 10,962,555 | `53ba37713dba35e561be9e457b9453df` |

Normalization keeps 30,104 input rows and emits 30,287 records after splitting
(183 extra biallelic rows). `vcf_concat` reproduces the original 30,104 rows.
`vcf_merge` writes 30,336 sites for the 51 samples (50 + HG001).

## Oracle: bcftools 1.19

Commands (reference and truth indexes built with `bcftools index -f -t`):

```bash
bcftools norm -m -any -f chr22_1000g.fa subset.vcf.gz -Ov -o norm.vcf
bcftools concat -a partA.vcf.gz partB.vcf.gz -Ov -o cat.vcf
bcftools merge -m both normalized.bgz.vcf.gz truth_norm.vcf.gz -Ov -o merge.vcf
```

| Step | Common records | Only bcftools | Only operator | GT differences | AC/AN differences |
| --- | --- | --- | --- | --- | --- |
| normalize | 30,286 | 0 | 0 | 0 | 0 |
| concat | 30,104 | 0 | 0 | 0 | 0 |
| merge | 30,336 | 0 | 0 | 1 | 1 |

Normalization is compared with REF/ALT upper-cased because `bcftools` keeps the
soft-masked lower-case bases of the reference and the operator upper-cases the
alleles; the alleles themselves are identical.

Two merge rows differ, both for the same multi-allelic overlap at
`22:17996285 A>ATCTC`:

- `FORMAT`: `bcftools` keeps `GT` only (the first file's FORMAT on that row),
  the operator writes the union `GT:DP:ADALL:AD:GQ:IGT:IPS:PS`. The `GT` values
  are identical.
- `INFO`: `bcftools` copies the original multi-allelic `AC=58;AN=100` on that
  row, the operator recounts `AC=59;AN=102` from the merged genotypes.

Both are documented semantics, not silent mismatches: the operator always
recomputes INFO for the merged sample set.

## Limitations

- Single chromosome slice; no site-level filtering by QUAL or depth.
- VCF must be bgzip-compressed with a tabix index; plain `.vcf` is accepted but
  the merge oracle path expects an index.
- `vcf_merge` merges exactly two files; sample names must be disjoint and the
  FORMAT fields are unioned, missing values become `.`.
- `vcf_concat` requires identical sample lists in identical order; it does not
  sort or deduplicate records.
- Ploidy is preserved per genotype; no phasing merge is attempted.
- Structural variants and symbolic alleles are passed through untouched.
