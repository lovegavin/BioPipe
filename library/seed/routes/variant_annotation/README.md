# Variant consequence annotation on 1000 Genomes chr22

## Data

| Role | File | Size (B) | SHA-256 |
| --- | --- | ---: | --- |
| Variants | `subset.vcf` | 10,350,044 | `88e6d3337c6e60ef0cce65ebe8852cda8e0b64c6186ba206a5bb9828f6672716` |
| Annotation | `gencode19_22.csq.gff` | 26,601,604 | `0df1955a627990254262c21e91f61d30b1720203257108409604dce8d6020f29` |
| Reference | `chr22_1000g.fa` | 52,330,662 | `51c376f6c0b898b23bc067f53d93ca801beabfb1d846898372837d37d5578829` |

`subset.vcf` holds 30,104 records from 1000 Genomes Phase 3 (chr22:17,000,000-18,000,000, GRCh37).
`gencode19_22.csq.gff` is GENCODE v19 chr22 (58,721 lines) with `biotype` copied from
`gene_type`/`transcript_type` so that `bcftools csq` can index it. `chr22_1000g.fa` is
UCSC hg19 chr22 renamed to `22`.

## Route (4 steps)

1. `variant_consequence` (VCF + GFF3 + FASTA) writes an annotated VCF with
   `CSQ`, `GENE`, `TX`, `AA` INFO fields.
2. `variant_impact_summary` counts consequences into a 2-D Form.
3. `export_results` exports that Form as `impact_summary.csv`.
4. `coding_variant_filter` keeps coding and splice consequences
   (444 of 30,104 records) as `coding.vcf`.

The annotated VCF (`11,294,645` B, md5 `e3bd77bbb36b59ca8e4ca1545f09ff83`) and the
filtered VCF (`198,502` B, md5 `8c7adbf0820fc6624ec2a837cf3c795d`) are native
`result_files`; `export_results` has no VCF writer, so only the summary is exported.

## Results

- 16,732 of 30,104 variants receive a non-intergenic consequence (55.6%).
- Classification counts (from `impact_summary.csv`, md5 `236220bb46238869ad56c7ae904c0024`):
  stop_gained 7, start_lost 2, splice_acceptor 5, splice_donor 9,
  inframe_deletion 1, missense 258, synonymous 162, 5_prime_UTR 74,
  3_prime_UTR 475, non_coding 1,679, intron 14,060, intergenic 13,372.
- Runtime 1.10 s total (consequence 0.98 s, summary 0.08 s, filter 0.04 s).

## Oracles

### Ensembl VEP GRCh37 REST

Queried through `https://grch37.rest.ensembl.org/vep/human/region` (GRCh37 must use the
`grch37` subdomain; the default host ignores `assembly=GRCh37`).

| Sample | Compared | Class agreement | AA agreement |
| --- | ---: | ---: | ---: |
| 500 random SNVs (275 with VEP terms) | 275 | 275/275 (100%) | - |
| 428 coding variants | 427 | 427/427 (100%) | 426/427 (99.77%) |

The single AA difference is a codon-number convention on the NMD transcript
`ENST00000465611.1` (this operator reports `177Q>177*`, VEP reports `178Q>178*`);
`bcftools csq` agrees with the operator's numbering here.

### bcftools csq 1.19

`bcftools csq -f chr22_1000g.fa -g gencode19_22.csq.gff -l` indexes 4,459 transcripts
and annotates 16,721 sites. After matching the operator's chosen transcript:

| Metric | Value |
| --- | --- |
| Sites with matching transcript | 429 |
| Coding/splice union | 407 |
| Consequence agreement | 391/407 (96.07%) |
| Amino-acid agreement | 388/391 (99.23%) |

Residual differences are annotation-granularity conventions: `csq` labels the introns of
non-coding transcripts `non_coding` (this operator keeps `intron`), and `csq` adds a
`splice_region` class within a few bases of an exon boundary that this operator does not
model separately.

CDS phase from GFF3 is honoured: `ENST00000465611.1` `22:17468873 G>A` yields
`165A GCC>GCT`, matching `bcftools csq` (`165A`) and the phase-2 first CDS segment.

## Conventions

- One consequence per variant: the most severe overlapping transcript (VEP-style).
  `bcftools csq` uses the canonical Ensembl transcript, so whole-cohort agreement is
  not a correctness metric; comparisons must be restricted to matched transcripts.
- Non-coding transcript introns are reported as `intron`; VEP uses
  `non_coding_transcript_intron`, `csq` folds them into `non_coding`.
- Splice donor/acceptor cover the two intronic bases at each end; a wider
  `splice_region` class is not modelled.
- Indels inside CDS are classified by `length % 3`; start-lost and in-frame deletion
  amino-acid strings follow this operator's own display convention.

## Reproduce

```bash
python scripts/run.py library/seed/routes/variant_annotation --memory-mb 4096
```
