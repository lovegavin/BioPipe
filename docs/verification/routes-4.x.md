# Route verification for BioPipe 4.x

This page records incremental, three-platform verification of operator library
routes added after the 4.0.3 release. Every row is produced from a real,
publicly available dataset; synthetic inputs are never counted as biological
evidence.

Registry baseline after the first batch: **721 operators / 102 readers / 7
packages / 25 routes**, `errors 0`, `warnings 108`. After the second batch:
**725 operators / 103 readers / 7 packages / 26 routes**, `errors 0`, `warnings
108`. After the third batch: **729 operators / 104 readers / 7 packages / 27
routes**, `errors 0`, `warnings 108`.

## Batch 1 - variant_qc_concordance

### Data provenance

| Source | Dataset | Subset | Size | SHA256 |
| --- | --- | --- | --- | --- |
| `query` | 1000 Genomes phase 3, chr22 (b37 slice distributed with the verification workdir) | `22:17,000,000-18,000,000`, 50 samples (49 random + NA12878) | 620,892 B, 30,104 records | `1b7c66cf2ba8e0aa0e683d4f89e98b9a9fa9fb7db74e428b1c58c975f4589a93` |
| `truth` | GIAB NA12878 NISTv3.3.2 GRCh37 high-confidence calls, `HG001_GRCh37_GIAB_highconf_...PGandRTGphasetransfer.vcf.gz` | `22:17,000,000-18,000,000`, sample `HG001` | 30,805 B, 846 records | `3479819a02009dca99eac878a6280bd674c27c829c4c44f8830e49e484a457f8` |

GIAB is distributed from
`https://giab.s3.amazonaws.com/release/NA12878_HG001/NISTv3.3.2/GRCh37/`.
The 1000 Genomes slice and the GIAB region both use b37 contig names without a
`chr` prefix.

Rebuild the inputs with `bcftools`:

```bash
bcftools view -r 22:17000000-18000000 -s NA12878,HG00096,... \
  chr22.first200k.vcf.gz -Oz -o query.vcf.gz
tabix -h -f https://giab.s3.amazonaws.com/release/NA12878_HG001/NISTv3.3.2/GRCh37/HG001_GRCh37_GIAB_highconf_CG-IllFB-IllGATKHC-Ion-10X-SOLID_CHROM1-X_v.3.3.2_highconf_PGandRTGphasetransfer.vcf.gz \
  22:17000000-18000000 | bgzip > truth.vcf.gz
tabix -p vcf truth.vcf.gz
```

### Route

`library/seed/routes/variant_qc_concordance/` contains the eight-step route:
`vcf_stats -> export_results -> vcf_filter -> export_results(native) ->
vcf_concordance -> export_results -> vcf_relatedness -> export_results`.

Run it with the standard task runner:

```bash
python scripts/run.py workdir/b1_route --check
python scripts/run.py workdir/b1_route --memory-mb 4096 --disk-mb 4096
```

### Results (identical on all three platforms)

| Step | Metric | Value |
| --- | --- | --- |
| `vcf_stats` | variants / SNPs / indels / other | 30,104 / 28,730 / 1,524 / 33 |
| | multiallelic / PASS | 172 / 30,104 |
| | transitions / transversions / Ts:Tv | 19,912 / 8,809 / 2.260415 |
| | mean QUAL / samples / chromosomes | 100.0 / 50 / 1 |
| `vcf_filter` | input / output / removed | 30,104 / 30,104 / 0 |
| | filtered VCF bytes | 10,349,708 |
| `vcf_concordance` | query ALT sites / truth ALT sites | 30,287 / 850 |
| | matched / truth-only / query-only | 797 / 53 / 29,449 |
| | duplicate query alleles skipped | 5 |
| | allele mismatches / genotype comparisons | 41 / 797 |
| | genotype discordant / concordance | 9 / 0.9887076537 |
| `vcf_relatedness` | samples / SNPs | 50 / 2,816 |
| | mean off-diagonal kinship | -0.026224 |
| | max off-diagonal kinship | 0.293938 |

Exported artifacts: `variant_stats.csv`, `concordance.csv`, `kinship.csv`
(50 x 50) and `filtered_variants.vcf`.

### Independent oracles

| Oracle | Version | Comparison | Result |
| --- | --- | --- | --- |
| `bcftools norm -m -any` + `bcftools stats` | 1.25 (srv), 1.19 (WSL) | allele-level SNP / indel / other counts | exact (28,730 / 1,524 / 33), Ts:Tv 19,919/8,811 = 2.26 |
| `bcftools view -H -i 'QUAL>=20 && FILTER="PASS"'` | 1.19 | retained records | exact (30,104) |
| `bcftools isec` on split query/truth VCFs | 1.25 | shared / truth-only / query-only | exact (797 / 53 / 29,490) |
| `plink2 --make-king-table counts` on the same biallelic SNP set (`bcftools view -m2 -M2 -v snps`, 2,816 sites) | 2.0.0-a.7.13 | 1,225 pair kinship coefficients | max abs delta 5e-7, mean abs delta 1.1e-7, Pearson 1.0 |
| plink2 full SNP set (2,837 sites, multiallelic REF dosage included) | 2.0.0-a.7.13 | 1,225 pairs | mean abs delta 0.0013, max 0.0056, Pearson 0.999935 (scope difference, not an error) |

Tolerances used for the gate: integer counts exact; kinship `abs(delta) <=
1e-5`. The same-variant-set comparison passes with a 20x margin.

### Platform notes

- WSL: Ubuntu 24.04, Python 3.12.14, bcftools 1.19, samtools 1.19.2.
- srv: Python 3.11.18 virtual environment, bcftools 1.25,
  `plink2 2.0.0-a.7.13`. The same commit was synced as a source archive; all
  eight step reports match WSL byte-for-byte apart from timing fields.
- Windows: Python 3.12.10, a Windows checkout; task runner and the Studio control
  API (`POST /api/v1/jobs`) both reproduce the same values. The API job was
  submitted by an agent token with `context`, `edit` and `run` scopes.
- All three runs use the same commit; compare scripts ignore paths, timings and
  `result_files` entries and report `DIFFS 0`.

### Platform gap fixed in this batch

`.vcf.gz` inputs were previously claimed by `VcfReader`, which decodes a
genotype matrix, so no operator could receive a raw VCF file. Batch 1 adds
`VcfFileReader` (`library/seed/src/reader/readers/vcf_file_reader.py`), a
metadata-only reader that returns a `FileArtifact` with representation `vcf`.
Routes select it explicitly with `reader: VcfFileReader`. Reader count moves
from 101 to 102; operator code and protocol v3 semantics are unchanged.

### Known limits

- `vcf_relatedness` intentionally restricts to biallelic SNPs, MAF >= 0.05,
  call rate >= 0.9, and the first 50 samples by default. plink2 includes
  multiallelic REF dosages, which explains the 21 extra sites in the full-set
  comparison; the same-set comparison removes that scope difference.
- `vcf_concordance` compares ALT alleles, not records. A query record with two
  ALT alleles contributes two sites; truth-only ALT alleles are counted
  separately.
- Duplicate query records with the same ALT are skipped and reported as
  `n_query_duplicates` instead of aborting the run.

## Batch 2 - sequencing_qc

### Data provenance

| Source | Dataset | Subset | Size | SHA256 |
| --- | --- | --- | --- | --- |
| `reads_1` | ENA `SRR001666`, Escherichia coli K-12 MG1655 paired-end reads | first 200,000 pairs | 8,291,336 B | `5b512b0bd02c906186c48aa76d20b3ba4d6f3423a317671523c0d01005571586` |
| `reads_2` | same run, mate 2 | first 200,000 pairs | 9,356,844 B | `1e35a3053055b4d229fa37b9367028251860c47b06a9a947309fc287722d8088` |
| `ecoli.fasta` | NCBI `GCF_000005845.2` (ASM584v2), E. coli K-12 MG1655 | complete genome | 4,699,745 B | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |

The 200,000-pair subset is a prefix of the real run, not synthetic data. Rebuild
it with:

```bash
curl -O https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR001/SRR001666/SRR001666_1.fastq.gz
curl -O https://ftp.sra.ebi.ac.uk/vol1/fastq/SRR001/SRR001666/SRR001666_2.fastq.gz
gzip -dc SRR001666_1.fastq.gz | head -n 800000 | gzip -1 > reads_1.fastq.gz
gzip -dc SRR001666_2.fastq.gz | head -n 800000 | gzip -1 > reads_2.fastq.gz
```

### Route

`library/seed/routes/sequencing_qc/` contains the nine-step route:
`fastq_stats -> export_results -> fastq_quality_profile -> export_results ->
fastq_adapter_scan -> export_results -> align_reads -> bam_flagstat ->
export_results`. `align_reads` runs `bwa index`, `bwa mem -5SP` and
`samtools view -b`; the `reads` source declares `mate_path: reads_2.fastq.gz`.

```bash
python scripts/run.py workdir/b2_route --check
python scripts/run.py workdir/b2_route --memory-mb 4096 --disk-mb 4096
```

### Results (identical on all three platforms)

| Step | Metric | Value |
| --- | --- | --- |
| `fastq_stats` | reads / bases | 200,000 / 7,200,000 |
| | length min / max / mean | 36 / 36 / 36 |
| | GC fraction | 0.5080722222 |
| | mean quality / Q20 / Q30 | 34.71771889 / 0.8753909722 / 0.7919225 |
| | reads containing N | 1,231 |
| `fastq_quality_profile` | cycles | 36 |
| | first-cycle mean quality | 39.893625 |
| `fastq_adapter_scan` | illumina / nextera / small-RNA reads | 2 / 2 / 2 |
| `align_reads` | BAM records | 400,000 |
| | wall time (WSL / srv) | 6.829 s / 16.119 s |
| `bam_flagstat` | total / primary / mapped | 400,000 / 400,000 / 372,959 |
| | read1 / read2 | 200,000 / 200,000 |
| | properly paired / both mapped | 0 / 354,394 |
| | singletons / duplicates / secondary / supplementary | 18,565 / 0 / 0 / 0 |

The four exported CSVs are byte-identical on all three platforms:

| Artifact | MD5 |
| --- | --- |
| `fastq_stats.csv` | `65e64ac9328a9cedb2985f94af00b5f1` |
| `quality_profile.csv` | `0aa3198dc73232eaa30b47f59ba06352` |
| `adapter_scan.csv` | `13547050dc7f753e2209f7097e67ea72` |
| `bam_flagstat.csv` | `59e1ce934f4e25256f546410ee8d7327` |

### Independent oracles

| Oracle | Version | Comparison | Result |
| --- | --- | --- | --- |
| Biopython `SeqIO` re-implementation | 1.86 | 10 summary statistics + 36 per-cycle mean qualities | abs delta 0.0 for every value |
| `seqkit stats -a` | 2.9.0 | reads, bases, length, Q20, Q30, GC, N bases | matches to the printed precision (87.54%, 79.19%, 50.81%, 6,153 N bases) |
| `cutadapt -a <adapter> -O 8 -e 0` | 5.2 | reads carrying each 3-prime adapter | exact: 2 / 2 / 2 |
| `samtools flagstat` | 1.19.2 | all 16 flagstat counters | exact for every counter |

The adapter comparison is the reason the operator anchors matches at the 3-prime
end: an anywhere-in-read 8-mer search reported 52 / 32 / 58 reads, which is
random background, while cutadapt and the 3-prime implementation both report 2.

### Platform notes

- WSL: Ubuntu 24.04, Python 3.12.14, bwa 0.7.17-r1188, samtools 1.19.2.
- srv: Python 3.11.18 virtual environment, bwa 0.7.19-r1273, samtools 1.22.1.
  The same commit was synced as a source archive; step reports differ only in
  artifact paths and `mtime_ns`.
- Windows: Python 3.12.10. bwa and samtools are not installed, so the alignment
  step is recorded as `SKIP(no bwa/samtools)` and the platform runs two
  sub-routes: `b2_fastq` (six FASTQ steps) and `b2_bam` (`BamFileReader` over the
  BAM produced on srv, then `bam_flagstat`). Both finish and reproduce the same
  CSV bytes.
- The Studio control API (`POST /api/v1/jobs`) is covered in batch 1; batch 2
  uses the task runner on all three platforms.

### Known limits

- `fastq_adapter_scan` reports reads whose 3-prime end matches an adapter
  prefix; internal adapter fragments are deliberately not counted.
- `bam_flagstat` parses BAM (BGZF) directly. SAM and CRAM inputs are out of
  scope for this operator.
- Windows cannot execute `align_reads` without bwa/samtools; this is an
  environment gate, not an operator failure.

## Batch 3 - ecoli_resequencing

### Data provenance

| Source | Dataset | Subset | Size | SHA256 |
| --- | --- | --- | --- | --- |
| `alignment` | ENA `SRR001666` (E. coli K-12 MG1655 paired-end), first 200,000 pairs | aligned with `bwa mem -5SP` to `GCF_000005845.2` | 19,134,169 B, unsorted BAM | `79e4140a615f96f839b065a9684bfe37939c056349da01772584f0e1d54b481e` |
| `reference` | `GCF_000005845.2_ASM584v2_genomic.fna` | complete genome | 4,699,745 B | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |

The BAM is the `sequencing_qc` output from batch 2 and is deliberately left
unsorted: every operator in this batch walks the records once and does not
require a coordinate-sorted file. Rebuild it with:

```bash
bwa index ecoli.fasta
bwa mem -5SP -t 4 ecoli.fasta reads_1.fastq.gz reads_2.fastq.gz \
  | samtools view -b -o alignment.bam
```

### Route

`library/seed/routes/ecoli_resequencing/` contains the eight-step route:
`alignment_coverage -> export_results -> alignment_insert_size ->
export_results -> pileup_variants -> export_results(native VCF) ->
consensus_sequence -> export_results(native FASTA)`.

| Operator | WSL | srv | Windows |
| --- | --- | --- | --- |
| `alignment_coverage` | 4,641,652 bp, 2.888806399x mean, 93.85117626% at 1x, 17.24461463% at 5x, 0.12829484% at 10x, max 16 | same | same |
| `alignment_insert_size` | 177,197 pairs, mean 37,955.427033, median 489, std 299,454.819115, p25 475, p75 503 | same | same |
| `pileup_variants` | 0 variants across 481,205 covered positions | same | same |
| `consensus_sequence` | 4,641,652 bases, 481,205 called, 0 substitutions | same | same |
| elapsed | 12.299 s | 28.416 s | 13.408 s |

### Byte identity

| Artifact | Size | MD5 |
| --- | --- | --- |
| `alignment_coverage.csv` | 265 B | `98a509ef3f676435a083b69b183d9dc7` |
| `alignment_insert_size.csv` | 226 B | `579ce9008724b364b7d55650d618ba9c` |
| `consensus_genome.fasta` | 4,719,059 B | `fea8bdcce398048b3fe26a2345fd66f4` |
| `consensus_variants.vcf` | 134 B | `9e2e2c8fe97ca3d5783cdecf279f4936` |

All four files are byte-identical on WSL, srv and Windows.

### Oracle

| Oracle | Version | Metric | Comparison |
| --- | --- | --- | --- |
| `samtools coverage` | 1.19.2 | mean depth / covered bases / coverage | 2.88881 / 4,356,245 / 93.8512% - exact |
| `samtools depth -a` | 1.19.2 | 1x / 5x / 10x bases, max depth | 4,356,245 / 800,435 / 5,955 / 16 - exact |
| `samtools view -f 0x41 -F 0x904` | 1.19.2 | insert-size n, mean, median, std, p25, p75 | 177,197 / 37,955.427033 / 489 / 299,454.819 / 475 / 503 - exact |
| `bcftools mpileup -q 0 -Q 20 -d 10000 \| bcftools call -mv` | 1.19.2 | variant calls | 0 calls - exact |
| `samtools consensus -m simple -d 5 -c 0.6 --min-BQ 20 --show-del yes -a` | 1.19.2 | consensus bases and substitutions | identical sequence, 481,205 called, 0 differences |

The consensus comparison exposed a real parsing trap in the oracle: without
`--show-del yes`, `samtools consensus` omits four deletion columns, shifts every
downstream base and produces 226,762 false differences. With the flag, the two
sequences agree at every position.

### Platform notes

- WSL: Ubuntu 24.04, Python 3.12.14, samtools 1.19.2, bcftools 1.19.
- srv: Python 3.11.18 virtual environment; the same commit was synced as a
  source archive and the route ran in 28.416 s.
- Windows: Python 3.12.10. The operators are pure Python, so the platform ran
  the full route against the same BAM bytes. The first Windows run produced
  CRLF files because `Path.write_text` translates newlines; both
  `consensus_sequence` and `pileup_variants` now use `write_bytes` with explicit
  `\n`, and all four artifacts are byte-identical again.

### Known limits

- `pileup_variants` and `consensus_sequence` work in reference coordinates:
  insertions are not represented, deletions keep the reference base, and a
  multi-allelic position is reduced to the majority base.
- Insert-size statistics do not require proper pairs; this BAM has zero properly
  paired reads by construction, so the median is the robust summary and the mean
  is inflated by chimeric pairs.
- Zero variants is the expected biological result here: SRR001666 is K-12
  MG1655 matching the reference at 2.9x mean depth, and `bcftools call` also
  reports zero.

## Batch 4 - pbmc_trajectory

### Data provenance

| Source | Dataset | Subset | Size | MD5 |
| --- | --- | --- | --- | --- |
| `embedding` | 10x Genomics PBMC3k (`pbmc3k_filtered_gene_bc_matrices.tar.gz`, 7,621,991 B) | PCA scores of 1,200 cells | 249,229 B | `34a94892dea773b88e9a51c8e229689e` |
| `clusters` | same | Leiden cluster id, 13 clusters | 23,095 B | `aa4df2e789e3f872e51b2cf46838d217` |
| `expression` | same | 300 highly variable genes | 2,542,469 B | `10a345c0631c53824840492acb187479` |
| `communication` | same | 29 ligand/receptor genes | 264,164 B | `8f163606afa7fd7350f98f9322f748e3` |
| `pairs` | 20 canonical immune ligand-receptor pairs | curated panel | 218 B | `7542f90474960d296ac6179ee068b7dd` |

Preparation (scanpy 1.12.5, igraph 1.0.0, leidenalg 0.12.0): keep cells with
>= 200 genes and genes in >= 3 cells (2,700 x 13,714); `normalize_total(1e4)`
and `log1p`; 300 HVG; `scale(max_value=10)`; PCA 20; 15-neighbour graph; Leiden
resolution 1.0 (13 clusters); fixed subsample of 1,200 cells with
`numpy.random.default_rng(0)`. The four CSV files and the pair panel are the
route inputs; they are reproduced by the steps above and are not shipped in the
repository.

### Route

`library/seed/routes/pbmc_trajectory/`:

```
pseudotime_dpt -> export_results -> paga_connectivity -> export_results
  -> trajectory_gene_trends -> export_results -> cell_communication
  -> export_results
```

The root cell is `AAACATACAACCAC-1`, the first barcode of the filtered matrix.

| Operator | WSL | srv | Windows |
| --- | --- | --- | --- |
| `pseudotime_dpt` | 1,200 cells, root `AAACATACAACCAC-1`, range 0..1 | same | same |
| `paga_connectivity` | 13 clusters, 1,200 cells | same | same |
| `trajectory_gene_trends` | 300 genes x 10 bins | same | same |
| `cell_communication` | 734 interactions, 13 clusters, 15/20 pairs | same | same |
| elapsed | 0.229 s | 6.175 s | 0.239 s |

The three export tables (PAGA, trends, communication) are byte-identical on all
three platforms:

| Artifact | Size | MD5 |
| --- | --- | --- |
| `paga_connectivity.csv` | 3,090 B | `55670bb0dc751630e551d1bf3f3fe95e` |
| `trajectory_gene_trends.csv` | 19,387 B | `67cd17e4aa94e8f500408475aa9854fc` |
| `cell_communication.csv` | 26,652 B | `35aa9b1425ca14994d3d2b640a3907c2` |

The pseudotime table differs only in floating-point text formatting across the
three NumPy builds (2.1.3, 2.4.6, 2.5.4); the values agree to 4.4e-16 (WSL vs
srv) and 4.0e-16 (WSL vs Windows), with Pearson 1.0 in both comparisons.

### Oracle

| Operator | Oracle | Version | Comparison |
| --- | --- | --- | --- |
| `pseudotime_dpt` | `sc.pp.neighbors(method="gauss")` + `sc.tl.diffmap(n_comps=10)` + `sc.tl.dpt` with the same root | scanpy 1.12.5 | Spearman **0.9507**, Pearson 0.5883, max abs 0.5915 |
| `paga_connectivity` | `sc.tl.paga(groups="cluster")` on the same neighbours and clusters | scanpy 1.12.5 | Pearson **0.9635**, max abs 0.4381 after max-scaling |
| `trajectory_gene_trends` | independent pandas groupby over the same bin edges | pandas 2.2.3 | max abs **9.9e-17**, identical NaN mask |
| `cell_communication` | independent pandas per-cluster means and the same product formula | pandas 2.2.3 | **734/734** interactions, 0 missing, 0 extra, max abs **2.2e-16** |

Pseudotime is ordinal: the rank correlation is the agreement measure and the
absolute scale differs because the operator builds an adaptive kNN graph
symmetric by maximum while scanpy builds a Gaussian-kernel graph. Both use the
Haghverdi et al. (2016) `lambda/(1-lambda)` component weights. PAGA
connectivities are normalised differently (our off-diagonal maximum is 1), so
the matrices are compared after the same scaling. There is no external
command-line oracle for pseudotime or communication scores on this dataset; the
scanpy implementations are independent codebases and the pandas recomputations
check the arithmetic directly.

### Platform notes

- WSL: Ubuntu 24.04, Python 3.12.14, NumPy 2.1.3.
- srv: Python 3.11.18 environment, NumPy 2.4.6. The route took 6.175 s because
  the DPT eigendecomposition uses a different LAPACK build; results are
  numerically identical.
- Windows: Python 3.12.10, NumPy 2.5.4, registry 733 operators / 104 readers /
  7 packages / 28 routes with `errors []`, `tests/test_extension366.py` 13
  passed. The first Windows attempt failed on a stale unquoted `task.yaml` left
  in the scratch directory, not in the builtin route; copying the route file
  fixed it.

### Known limits

- `pseudotime_dpt` uses the supplied embedding; it does not normalise, select
  genes or compute the embedding itself.
- `paga_connectivity` is a normalised kNN edge count, not a statistical test.
- `trajectory_gene_trends` averages equal-width pseudotime bins; empty bins are
  `NaN`, which is why the earliest bins are sparse.
- `cell_communication` scores ligand/receptor co-expression between clusters; it
  is not a permutation test and does not model complexes or diffusion.
- The 1,200-cell subsample is a runtime compromise; the pair panel is a
  demonstration subset, not a complete interaction database.

## Batch 5 — Structure validation (missing residues, alternate conformers, cis peptides)

Three coordinate-level checks that only read the atoms present in a PDB file.
No coordinates are rebuilt from a tensor and no structure file is written.

### Inputs

| Source | PDB | Size | SHA256 | Why it is used |
| --- | --- | --- | --- | --- |
| `structure_1mel` | [1MEL](https://files.rcsb.org/download/1MEL.pdb) | 361,017 B | `321aa847a20535c018b12cf340d2e057628dce42b4005c185916dd17bdd24de4` | Camelid VHH dimer with contiguous numbering; gap negative control and cis-peptide positive control |
| `structure_3di3` | [3DI3](https://files.rcsb.org/download/3DI3.pdb) | 256,365 B | `9ef4a39b6c66186cc5efb17d0b2a12f08b0b0ebd6c4ec851c6b0b68c0efd03b9` | IL-7 / IL-7R-alpha complex with one internal gap in chain A |
| `structure_2vb1` | [2VB1](https://files.rcsb.org/download/2VB1.pdb) | 447,444 B | `cb971a808effff36ae4c2e7030a6608e7a78f55a1c4eb9ccd669872dbd66aa37` | 0.65 A lysozyme with four alternate-location labels |

Downloaded from RCSB on 2026-11-07.  Inputs stay in the run directory and are
not committed.

### Route

`structure_validation` (8 steps): `structure_missing_residues` on 1MEL and
3DI3, `structure_altloc_inventory` on 2VB1, `structure_cis_peptides` on 1MEL;
each operator is followed by `export_results`.

### Results

| Step | Result | WSL | srv | Windows |
| --- | --- | --- | --- | --- |
| `structure_missing_residues` (1MEL) | 0 gaps, 0 missing residues, 4 chains | same | same | same |
| `structure_missing_residues` (3DI3) | 1 gap `A:99-121`, 23 missing residues | same | same | same |
| `structure_altloc_inventory` (2VB1) | 4 conformers, 1,440 altloc atoms, 49 residues with alternates | same | same | same |
| `structure_cis_peptides` (1MEL) | 514 bonds, 2 cis (`A:30-31`, `B:30-31`), 0 skipped | same | same | same |
| elapsed | | 0.066 s | 0.350 s | 0.076 s |

The four exported CSV files are byte-identical on WSL, srv and Windows:

| Artifact | Size | MD5 |
| --- | --- | --- |
| `missing_residues_1mel.csv` | 25 B | `59038a06a0ed30bd5d8a1ad3c795b96f` |
| `missing_residues_3di3.csv` | 51 B | `87f672f88193e95dd7c1f1890b35bf61` |
| `altloc_inventory_2vb1.csv` | 345 B | `23010e91a328bb534d470e4a40ac25d7` |
| `cis_peptides_1mel.csv` | 26,121 B | `261a9dff0d651e4f78fb158ad22e2e56` |

### Oracle

`gemmi` 0.6.5 parses the same PDB files through an independent code path and
recomputes residue numbering, alternate locations and omega dihedrals.

| Operator | Oracle | Comparison |
| --- | --- | --- |
| `structure_missing_residues` | gemmi residue numbering plus RCSB `REMARK 465` | identical gap `A:99-121` / 23 missing; every missing residue is declared in `REMARK 465` (66 entries); 1MEL and 2VB1 have zero internal gaps |
| `structure_altloc_inventory` | gemmi altloc inventory | identical labels `{_, A, B, C}`; max abs difference 1.5e-8 across atom counts, residue counts, min/max/mean occupancy |
| `structure_cis_peptides` | gemmi `calculate_dihedral` converted from radians, `abs(omega) <= 30` | 514 bonds on both sides; 2 cis on both sides (`A:30-31`, `B:30-31`); max abs omega difference 7.6e-6 degrees; 0 label or cis-flag mismatches |

Raw comparison output: `workdir/b5_oracle.json`.  The oracle needs `gemmi`, which
is installed in the WSL analysis environment but not in the Windows runtime, so
the oracle comparison is a WSL-side check; the byte-identical exports above
carry the same values to the other two platforms.

### Platform notes

- WSL: Ubuntu 24.04, Python 3.12.14, NumPy 2.1.3, gemmi 0.6.5.
- srv: Python 3.11.18, the same 8/8 result, 0.350 s.
- Windows: Python 3.12.10; registry 736 operators / 104 readers / 7 packages /
  29 routes with `errors []`; `tests/test_extension367.py` 10 passed.
- An earlier ad-hoc inspection script reported spurious gaps for 1MEL and 3DI3;
  the raw PDB numbering and the gemmi recount above replace those numbers.

### Known limits

- Only internal numbering gaps are visible; terminal truncation leaves no trace
  in a coordinate file and cannot be inferred.
- Non-standard residues and insertion codes are reported by PDB numbering; a
  chain that restarts numbering is reported as one gap.
- Alternate conformers are reported as they appear in the file.  A structure
  without `altloc` identifiers yields a single blank row, which is the correct
  result for that file; it does not prove the crystal had no disorder.
- Cis-peptide detection needs `CA`, `C`, `N`, `CA` on both sides of the bond;
  bonds across a gap or with missing backbone atoms are counted in `n_skipped`.

---

## Batch 6 — Golub co-expression network (WGCNA-style)

`golub_coexpression` adds four co-expression operators on top of the Golub
(1999) acute leukemia cohort: scale-free topology fit, TOM-based module
detection, module eigengenes and module-trait correlation.

### Data

| Source | Bytes | SHA256 |
| --- | ---: | --- |
| `input/expression.csv` | 4,103,343 | `1331609e00d99943803f45f3b5677cfd6cc798600dd9bbf305e0893a01a82731` |
| `input/traits.csv` | 364 | `9b9c1df4a2c471dd54457b9b05cc4244441ac6e418996d78fba0cd9ca54151dd` |

The matrix is the `Golub1999.rds` ExpressionSet distributed by the
IowaBiostat `golub` package (Git LFS object
`de43dd8798c09a681b593c052ebf83acda9f0a691ca8e3ccd779a3a4ae0633b0`,
3,712,634 B), converted with `rdata` 0.5.2: 72 samples (47 ALL, 25 AML) x
7,129 Affymetrix probes. `traits.csv` carries the AML indicator (AML = 1).

### Route

| # | Step | Key parameters |
| --- | --- | --- |
| 1 | `wgcna_soft_threshold` | `max_features=2000`, powers 1-10,12,14,16,18,20 |
| 3 | `coexpression_modules` | `beta=6`, `cut_height=0.99`, `merge_threshold=0.75`, `min_module_size=30` |
| 5 | `module_eigengenes` | `scale=true` |
| 7 | `module_trait_correlation` | Pearson vs `class` |

Every operator is followed by `export_results` to CSV. WSL reference run:
8/8 steps, 0.734 s total (0.201 / 0.291 / 0.010 / 0.224 s).

### Results

Modules: `0:1518 1:126 2:96 3:91 4:68 5:54 6:47` (module 0 is grey).

| Module | r (AML) | p |
| --- | ---: | ---: |
| 1 | 0.827996 | 2.951607e-19 |
| 2 | -0.721153 | 9.034709e-13 |
| 3 | -0.474847 | 2.504351e-05 |
| 4 | 0.176259 | 1.385925e-01 |
| 5 | -0.120287 | 3.141929e-01 |
| 6 | 0.518194 | 3.127378e-06 |

### Cross-platform

| Artifact | WSL | srv | Windows |
| --- | --- | --- | --- |
| `coexpression_modules.csv` | `9ca09112dd69fbdb0a91ee17a05acce7` (24,586 B) | same bytes | same bytes |
| `wgcna_soft_threshold.csv` | `fb88b54ab184fef543c1ba430ae4e530` (1,846 B) | `bd6c5176966dbf2f68d40b170cf4a4dc` (1,842 B) | `de7a116637bf5798b73506c578c8b266` (1,839 B) |
| `module_eigengenes.csv` | `5720ff6300d2ff4f0b07fca8bec3e9cf` (8,510 B) | `3ff4fded0fbdf05cd39edeab679ddc24` (8,534 B) | `05600983743ddad0589b377e3b50d222` (8,526 B) |
| `module_trait_correlation.csv` | `66627a7e4b175a593a39f8937cea91cc` (376 B) | `ed15c5b749b9625fa71cd657f69a232e` (374 B) | `893758ec5765cfececf7b7a594ecd9b6` (374 B) |

Only the module table is byte-identical: the other three files differ in
float text length because the three hosts use different NumPy/Pandas builds
(2.1.3/2.2.3/2.5.x). Values agree after parsing:

| Comparison | Max abs difference |
| --- | --- |
| soft threshold (WSL vs srv) | `r_squared` 1.1e-16, `slope` 3.1e-15, k columns 0 |
| soft threshold (WSL vs Windows) | `r_squared` 1.1e-16, `slope` 3.1e-15, `max_k` 7.1e-15 |
| eigengenes (both) | 1.78e-14 |
| trait correlation (both) | r 2.2e-16, p 4.4e-16 (srv) / 3.9e-16 (Windows) |
| module labels (both) | 2,000/2,000 in the same order |

Elapsed: srv 4.334 s (0.588 / 1.699 / 0.698 / 1.338 s; the eigengene SVD is
slower on the cluster BLAS), Windows 1.516 s (0.678 / 0.286 / 0.013 / 0.522 s).
Windows ran the same tarball (`repo_b6.tgz`) and reported registry
`740 operators / 104 readers / 7 packages / 30 routes`, errors 0,
108 pre-existing warnings.

### Oracles

Independent implementation: **WGCNA 1.73** (R 4.3, conda-forge), same 2,000
variable probes, unsigned network, `pickSoftThreshold` +
`adjacency` + `TOMsimilarity` + `hclust`/`cutree` + `mergeCloseModules`.

| Quantity | Max abs difference |
| --- | --- |
| `mean_k`, `median_k`, `max_k` | 1.7e-13 / 1.7e-13 / 4.0e-13 |
| scale-free `r_squared`, `slope` | 5.6e-16, 2.3e-14 |
| module labels | identical, 2,000/2,000 |
| eigengene correlation with `ME1`-`ME6` | 1.0 (sign-aligned z 3.1e-14) |
| trait `correlation` / `p_value` | 4.8e-15 / 4.0e-13 relative |

`tests/test_extension368.py::test_scale_free_fit_matches_wgcna_reference` pins
the histogram regression against values printed by `scaleFreeFitIndex()`.
The scale-free fit reproduces R's `cut(k, 10)` behaviour, including the
minimum k in the first bin; dropping it changes `r_squared` by 0.0016.

Duplicate probe names are renamed differently by Pandas (`ACTB.1`) and R
`write.csv` (`ACTB.1`, `ACTB.3`, ...), so a raw name join overcounts
mismatches; labels agree for all 1,900 base names.

### Known limits

- Unsigned network restricted to the 2,000 most variable probes.
- `cut_height` and `merge_threshold` are fixed in the route, not tuned.
- The grey module is excluded from the eigengene table.
- Module-trait correlation is unadjusted Pearson; no batch, sex or age
  covariates exist in this ExpressionSet.

## Batch 7 — E. coli genome annotation (density, intergenic, promoters, CDS)

Operators: `genome_gene_density`, `genome_intergenic_regions`,
`genome_promoter_extract`, `genome_cds_check`; route `ecoli_annotation`
(8 steps, every result exported through `export_results`; promoters export as
FASTA from `info.sequences`).

### Inputs

| File | Source | Size | SHA256 |
|---|---|---|---|
| `ecoli.gff` | NCBI RefSeq `GCF_000005845.2_ASM584v2_genomic.gff.gz` (unpacked, 9,531 lines) | 2,314,238 B | `68d25735ccde6d37af68613dca57a588ae69423f0ecee99b0f29d596eff7accb` |
| `ecoli.fasta` | NCBI RefSeq `GCF_000005845.2_ASM584v2_genomic.fna.gz` (`NC_000913.3`, 4,641,628 bp) | 4,699,745 B | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |
| `protein.faa.gz` (oracle only) | NCBI RefSeq `GCF_000005845.2_ASM584v2_protein.faa.gz` | 902,395 B | — |

### Results (WSL)

| Step | Value | Time |
|---|---|---|
| `genome_gene_density` | 465 windows, 4,506 gene records, 4,918 feature hits | 0.012 s |
| `genome_intergenic_regions` | 3,680 gaps, 611,155 bp | 0.043 s |
| `genome_promoter_extract` | 4,506 promoters, mean 100.0 bp | 0.119 s |
| `genome_cds_check` | 4,340 CDS; length_ok 4,319, start_ok 4,311, stop_ok 4,319, internal stops 12 | 0.185 s |

### Three platforms

| Platform | Steps | Total | Result |
|---|---|---|---|
| WSL (Python 3.12, bedtools 2.31.1) | 8/8 | 0.37 s | reference |
| srv (Python 3.11.18, numpy 2.4.6) | 8/8 | 0.92 s | identical |
| Windows (Python 3.12) | 8/8 | 0.55 s | identical |

Every exported artifact is byte-identical on all three platforms:
`gene_density.csv` 43,885 B `82f02ba5c1610c46b22164f6fdd70987`,
`intergenic_regions.csv` 124,971 B `cfed512078dabe00c8d013cedc7e6a1e`,
`promoters.fasta` 500,166 B `64dc55e375d16b3f9183d503204520c1`,
`cds_check.csv` 125,504 B `b73adcb3a055b572a95f23a1a957cbd0`.

Registry after the batch: **744 operators / 104 readers / 7 packages / 31 routes**,
errors 0, warnings 108; Windows check reports the same counts.

### Oracle checks

| Check | Implementation | Result |
|---|---|---|
| Window density | `bedtools makewindows` + `bedtools coverage` 2.31.1 | 465/465 windows, 0 mismatched (4,918 hits) |
| Intergenic gaps | `bedtools complement` 2.31.1 | 3,680 gaps / 611,155 bp identical |
| Promoters | `bedtools getfasta -s` 2.31.1 | 4,506/4,506 sequences identical, 0 mismatched |
| CDS length/start/stop | Biopython 1.88 `Seq.translate(table=11)` | 4,340/4,340 records identical |
| Protein identity | RefSeq proteome (4,259 proteins) | 4,288/4,340 CDS translate to an exact RefSeq protein |

The 52 unmatched CDS are 21 partial records (length not a multiple of three)
and 31 duplicate/alternative-frame annotations, plus selenocysteine entries
that RefSeq renders with `U`. Alternative CDS rows share a `locus_tag`
(`b0149`, `b0240`, `b4587`), so comparisons are positional rather than
name-based.

### Known limits

- Promoters come from GFF `gene` features only; no operon, UTR or TSS data.
- Upstream windows are clipped at contig boundaries; matrix rows are padded
  with `N`, `info.sequences` keeps the clipped string.
- CDS rows sharing a `locus_tag` are disambiguated with `#2`, `#3` suffixes.
- Internal stops are reported, not treated as errors (pseudogene fragments).
- The final density window of a contig may be shorter than 10 kb.

## Batch 8 — ATAC-seq QC (fragment size, TSS enrichment, peak quality)

New operators `atac_fragment_size`, `atac_tss_enrichment` and
`atac_peak_quality` under route `atac_qc`. Before this batch the library had no
ATAC-specific operator (only `motif_scan`, `peak_nearest_gene` and
`genome_promoter_extract`).

### Data

| Input | Source | Size | SHA256 |
|---|---|---|---|
| `ENCFF415FEC.bam` (GM12878 ATAC rep1, GRCh38, ENCODE4 v1.9.1) | `https://encode-public.s3.amazonaws.com/2021/02/24/e49caba2-1585-4e61-bafa-ff922467202c/ENCFF415FEC.bam` | 2,515,550,487 B | `08078e26e6cce95bf959d38941ff37693134601566193ef06851a9a3da910485` |
| `ENCFF945SYZ.bed.gz` (IDR thresholded peaks) | `https://encode-public.s3.amazonaws.com/2021/02/24/daad6883-45c9-4063-a558-fcd2596e66a1/ENCFF945SYZ.bed.gz` | 3,476,303 B (gzip) | `d3312c42b0cc241d25b56fd032b026039388d7e3cfe4a1c8457b84a7b49d6fb9` (BED, 9,819,405 B) |
| `tss.bed` (UCSC hg38 refGene, gene-level TSS) | `https://hgdownload.soe.ucsc.edu/goldenPath/hg38/database/refGene.txt.gz` | 8,668,756 B (gzip) | `a8ef7e106bd0c6ac2173302050fc8248def177dafdc17b42ab3f3a93b4d40b14` (BED, 998,500 B) |

The BAM md5 `aca6bde5b395777573e7cf94a04c2024` equals the ENCODE-published
checksum and `samtools quickcheck` passes. Peaks are the released IDR set
(155,153 regions). TSS positions are gene-level: `txStart` on the plus strand,
`txEnd - 1` on the minus strand, restricted to chr1–22, X and Y (28,278 genes).

### Route

| Step | Operator | Inputs | Parameters |
|---|---|---|---|
| 1 | `atac_fragment_size` | BAM | `min_mapq=30`, `max_length=1000`, `exclude_duplicates=true` |
| 2 | `export_results` | step 1 | CSV |
| 3 | `atac_tss_enrichment` | BAM, TSS BED | `flank=500`, `bin_size=10`, `min_mapq=30` |
| 4 | `export_results` | step 3 | CSV |
| 5 | `atac_peak_quality` | BAM, peak BED | `min_mapq=30` |
| 6 | `export_results` | step 5 | CSV |

### Results (WSL)

| Metric | Value |
|---|---|
| fragments (<= 1000 bp) | 22,737,035 |
| mean / median length | 266.7552 / 209 |
| NFR (< 100 bp) | 0.269817 |
| mononucleosome (180–247) | 0.155362 |
| dinucleosome (300–400) | 0.111612 |
| nucleosome (>= 147) | 0.635754 |
| TSS bins | 28,278 x 100 |
| TSS center mean | 3.938662564537803 |
| TSS flank mean | 1.1012766107928424 |
| TSS score (center/flank) | 3.576451661587764 |
| peaks | 155,153 |
| total peak bp / mean / median | 138,896,175 / 895.2207 / 847 |
| fragments in peaks | 14,522,524 |
| FRiP | 0.6353586420248108 |
| fragments per peak | 93.6013 |

### Oracles

| Quantity | Oracle | Agreement |
|---|---|---|
| Fragment lengths | `samtools view -f 0x1 -F 0xD04 -q 30` + awk: 22,857,207 fragments; per-length histogram 0..1000 | max abs per length **0**; sum 6,065,222,189 identical |
| Fragment count <= 1000 bp | same oracle | 22,737,035 = 22,857,207 - 120,172 long fragments |
| Peak widths / counts | direct BED parsing | n, total bp, mean, median identical |
| FRiP numerator | `bedtools intersect -u -a fragments -b peaks` 2.31.1 | 14,522,524 identical; FRiP exact |
| TSS profile | `bedtools makewindows` (100 x 10 bp around each TSS) + `bedtools intersect -sorted -c` | max abs profile **0.0**, Pearson **1.0** |

The first TSS oracle run disagreed only in bin 0 (offset -495) because windows
whose start was negative were dropped; clamping the window start to 0 made all
100 offsets exact.

### Three-platform runs

| Platform | fragment | TSS | peak | Note |
|---|---|---|---|---|
| WSL (Python 3.12, NumPy 2.1.3) | 96.5 s | 100.5 s | 97.4 s | 6/6 |
| srv (Python 3.11.18, NumPy 2.4.6) | 210.0 s | 223.0 s | 218.9 s | 6/6, total 652.4 s |
| Windows (Python 3.12, NumPy 2.5.4) | 106.993 s | 113.242 s | 107.844 s | 6/6, total 328.0 s |

| Export | WSL md5 | srv md5 | Windows md5 |
|---|---|---|---|
| fragment histogram | `8aaf381251b6794de1088979d9d60d5c` | same | same |
| peak statistics | `62093a237b5e98792069a210dd31934c` | same | same |
| TSS matrix | `db313a0be3ededf0daff48a05b86add7` (12,043,431 B) | `b771402786a8d93dbc7db7f96a5be738` (12,043,529 B) | same as srv |

The TSS matrix differs only in text length (pandas float formatting between
NumPy/pandas versions); the parsed matrices agree with `max abs 0.0` and
Pearson `1.0`.

### Known limits

- `max_length` defaults to 1000 bp; 120,172 longer fragments are excluded. Use
  `max_length >= 2000` for full fragment counts.
- Only primary, mapped, non-duplicate read pairs with `TLEN > 0` are counted;
  singleton and secondary alignments are ignored.
- TSS windows are clipped at contig boundaries; a TSS closer than `flank` to
  the start contributes fewer positions but stays in the matrix.
- Peaks are taken as given (ENCODE IDR here); FRiP uses any overlap between a
  fragment and a peak, not midpoint containment.
- The BAM must be coordinate-sorted for sensible results (not enforced).

## Batch 9 - model selection and feature ablation (breast cancer)

### Data

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `input/X.csv` | 122,657 | 30 standardized-input features for 569 samples (sklearn breast_cancer, public) |
| `input/y.csv` | 4,566 | 569 labels, 357 benign / 212 malignant |

Both files are derived from the public scikit-learn 1.6.1 dataset (no private data).

### Route `b9_ml` (8 steps)

`ml_stratified_folds` -> export, `ml_train_test_split` -> export,
`ml_logistic_fit` (standardized, C=0.01) -> export,
`ml_feature_ablation` (log-loss delta) -> export.

### Results

- folds: 5 stratified folds, sizes 114/114/114/114/113 (seed 0).
- split: 426 train / 143 test.
- logistic: accuracy 0.956063, ROC AUC 0.994160, 16 L-BFGS iterations.
- ablation top-3: worst texture, worst concave points, worst radius.

### Oracle (scikit-learn 1.6.1)

| Comparison | Result |
| --- | --- |
| StratifiedKFold assignment | identical, 0 mismatches |
| StratifiedShuffleSplit assignment | identical, 426/143 |
| logistic coef / intercept | max abs 9.45e-09 / 2.29e-09 |
| predicted probability | max abs 2.90e-08 |
| per-feature log-loss delta | max abs 3.34e-09, top-3 identical |

### Three platforms

| Platform | Elapsed (s) | Notes |
| --- | ---: | --- |
| WSL (numpy 2.1.3) | 1.74 | folds 0.001, split 0.001, logistic 0.057, ablation 1.683 |
| srv (numpy 2.4.6) | 0.13 | 8/8 |
| Windows (numpy 2.5.4) | 1.42 | 8/8 |

Fold and split exports are byte-identical on all three platforms. Logistic and
ablation CSVs differ only in last-digit float formatting: WSL vs srv max abs
1.1e-13 (coef 1.1e-16), WSL vs Windows 1.1e-16.

### Fixes found by the batch

- `fit_logistic` gradient was missing the `C` factor: correct at C=1, wrong at
  any other regularization strength. Regression: coefficient error dropped from
  0.09 to 9.5e-09 at C=0.01.
- `roc_auc` used `getattr(np, "trapezoid", np.trapz)`, which evaluates the eager
  default and crashes on numpy >= 2.4 where `np.trapz` is removed; replaced by
  an explicit trapezoid sum.
- `log_loss` clip aligned with scikit-learn (1e-15).

### Limitations

- Unstandardized coefficients are not identifiable because features are highly
  collinear; only probabilities are comparable. The route standardizes both.
- Ablation is a refit-cost importance, not a causal effect.

## Batch 10 - model validation and multiple testing (`ml_validation`)

### Data

| file | bytes | sha256 |
|---|---|---|
| `input/X.csv` | 122,657 | `ba62af1ee96f9315fb5d5fe469f65494538823314fb5e8d04330773232654d08` |
| `input/y.csv` | 4,566 | `f87fc0934dbc7af40dd99341db8abce9aa4567bf9fbd9682a10876d7828f01d8` |
| `input/pvalues.csv` | 844 | `2106106ef5d9603581e01d5532846c554ca2716fa64df9d8327f475fb87b3b73` |

Public scikit-learn breast-cancer table (569 samples, 30 WDBC features; 357
benign / 212 malignant). The p-value column is a Welch t-test per feature,
computed once at preparation time and versioned with the route.

### Route

Six steps: `ml_learning_curve` and `ml_grid_search` over five stratified folds
(seed 0, C=0.01 standardized), `stats_fdr` with Benjamini-Hochberg, each
followed by `export_results` to CSV. Folds are generated by the operator with
the same stratified shuffle rule as scikit-learn, so the oracle comparison is
element-wise.

### Results

| quantity | value |
|---|---|
| learning-curve sizes | 91, 182, 273, 364, 455 |
| test accuracy at 91 / 455 | 0.926161 / 0.949061 |
| best C | 1.0 (mean accuracy 0.978916, std 0.014245) |
| grid candidates | 0.001, 0.01, 0.1, 1, 10 |
| BH rejections (alpha 0.05) | 26 of 30 |
| adjusted p range | 3.18e-95 .. 0.887 |

### Oracles

| check | oracle | result |
|---|---|---|
| fold/size alignment | `sklearn.model_selection.StratifiedKFold` | sizes identical |
| learning-curve train mean | sklearn `LogisticRegression` (tol 1e-10) | max abs 1.11e-16 |
| learning-curve test mean / std | sklearn | max abs 1.11e-16 / 8.59e-17 |
| grid mean / std | sklearn manual CV | max abs 1.11e-16 / 5.20e-17 |
| best C | sklearn | both 1.0 |
| BH adjusted p | `statsmodels.stats.multitest.multipletests` | max abs 1.11e-16; 26/30 rejected |

`workdir/b10_oracle.json` stores the full comparison.

### Three platforms

| platform | elapsed | exports |
|---|---|---|
| WSL (numpy 2.1.3) | 0.025 / 0.002 / 0.053 / 0.001 / 0.000 / 0.001 s | curve / grid / fdr |
| srv (numpy 2.4.6) | 0.051 / 0.002 / 0.197 / 0.004 / 0.001 / 0.001 s | same |
| Windows (numpy 2.5.4) | 0.048 / 0.003 / 0.132 / 0.003 / 0.000 / 0.002 s | same |

All three exports are byte-identical across platforms:

| file | bytes | md5 |
|---|---|---|
| `ml_learning_curve.csv` | 504 | `13b41d8a4fe0fda5a7171fe1fc673f7d` |
| `ml_grid_search.csv` | 281 | `d0616bbb2bff7cab8965ce411b7fc2d7` |
| `stats_fdr.csv` | 1,656 | `6e8cb9312689889b5f68a90a5c2be5ca` |

### Defect found and fixed

The L-BFGS gradient in `_ml_utils.fit_logistic` omitted the penalty weight
(`grad = X.T @ (sigmoid - y)` instead of `C * X.T @ (sigmoid - y)`). With C=1
the two agree, so the earlier logistic route passed; with C=0.01 the fitted
coefficients were wrong by up to 0.5. The fix is covered by the standardized
logistic comparison (coefficient max abs 9.45e-9 against sklearn).

### Limits

- Coefficients are judged only after standardization, because the WDBC
  features are strongly collinear.
- `stats_fdr` implements BH, BY, Holm and Bonferroni; permutation-based
  correction is out of scope.

## Batch 11 — read preprocessing (FASTQ quality, adapter, dedup)

Operators: `fastq_quality_trim`, `fastq_adapter_trim`, `fastq_deduplicate`.
Route: `read_preprocessing` (6 steps, one source and three export branches).

### Data

| File | Size | SHA-256 |
| --- | --- | --- |
| `input/reads_1.fastq.gz` | 8,291,336 B | `5b512b0b…` |
| `input/reads_2.fastq.gz` | 9,356,844 B | `1e35a305…` |

First 200,000 pairs of ENA `SRR001666` (Illumina 36 bp, *E. coli*); the route
uses mate 1, mate 2 is retained for downstream alignment routes.

### Results (200,000 reads)

| Operator | Result | WSL | srv | Windows |
| --- | --- | --- | --- | --- |
| `fastq_quality_trim` | 194,355 kept / 6,687,525 bases / 512,475 trimmed bases | 0.385 s | 1.188 s | 0.432 s |
| `fastq_adapter_trim` | 3,244 with adapter / 7,189,076 bases / 10,924 trimmed bases | 4.995 s | 9.954 s | 6.925 s |
| `fastq_deduplicate` | 197,031 unique / 2,969 duplicates (0.014845) | 0.318 s | 0.904 s | 0.324 s |

### Oracles

- **cutadapt 5.2** (`-q 20 -m 20`): 194,355 reads / 6,687,525 bases; output
  FASTQ md5 `d4c039de4822593401950fc92abb1f2c` — byte-identical to the operator.
  `quality_trimmed` 433,109 excludes bases lost with dropped short reads; adding
  those 79,366 bases gives 512,475.
- **cutadapt 5.2** (`-a AGATCGGAAGAGCACACGTCTGAACTCCAGTCAC -O 3 -e 0 --no-indels`):
  3,244 reads with adapter / 7,189,076 bases; output md5
  `5b492c0d44347932bc7e79858c102a6f` — byte-identical.
- **seqkit 2.9.0** (`fx2tab | cut -f2 | sort -u`): 197,031 unique sequences.
  `seqkit rmdup -s` reports 195,398 because it also collapses reverse
  complements; the operator offers `collapse_reverse_complements` (default
  `false`) for that convention.

### Cross-platform byte comparison

| Artifact | Size | md5 (WSL / srv / Windows) |
| --- | --- | --- |
| `quality_trimmed.fastq` | 24,399,755 B | `d4c039de4822593401950fc92abb1f2c` |
| `adapter_trimmed.fastq` | 25,723,743 B | `5b492c0d44347932bc7e79858c102a6f` |
| `dedup_summary.fastq` | 25,362,382 B | `2482cad759730f347c837e9d24a8bcd0` |
| `fastq_quality_trim.csv` | 373 B | `2819a3d3b87db36c828c658d4ac05f02` |
| `fastq_adapter_trim.csv` | 355 B | `f04eff5feb9d55a515777232ac00652d` |
| `fastq_deduplicate.csv` | 290 B | `03a778759c76b03d5382c7c922b28496` |

### Notes and limitations

- FASTQ export is a native artifact (`result_files`); the summary Form is
  exported to CSV. `export_results` does not carry FASTQ text into CSV.
- Adapter matching is ungapped and 3'-anchored; `max_mismatches` applies to
  partial overlaps.
- Deduplication is exact-sequence by default; UMI-aware collapse is out of
  scope.

## Batch 12 - GM12878 interval annotation

### Data

| Source | File | Size | SHA256 | Records |
| --- | --- | --- | --- | --- |
| IDR peaks | `input/peaks.bed` | 9,819,405 B | `d3312c42b0cc241d25b56fd032b026039388d7e3cfe4a1c8457b84a7b49d6fb9` | 155,153 |
| Feature classes | `input/features.bed` | 15,479,361 B | `32cd7272ca283b67785ddc2f5acdc00d3b7f795e1aa2f791f7e793588f3b685e` | 520,033 |
| rep1 peaks | `input/rep1.bed.gz` | 2,427,146 B | `d54b59dfd4efbc3459e6e14bb9fdc45df5927c94f9ac428be517b83e0fbb9979` | 107,121 |

`features.bed` is derived from UCSC hg38 `refGene.txt.gz` (8,668,756 B): a
strand-aware promoter (TSS +/- 1 kb), 5' UTR, CDS, 3' UTR, exons and introns
per transcript, merged per class with the class name in column 4. Merged rows:
promoter 29,879, utr5 23,580, cds 18,764, utr3 23,547, exon 242,251,
intron 182,012.

### Route

`gm12878_interval_annotation`: peaks -> `interval_annotate` -> export;
peaks + features -> `interval_coverage` -> export; rep1 + peaks ->
`interval_jaccard` -> export. Six steps.

### Results

Annotation priority promoter, utr5, cds, utr3, exon, intron; 155,153 peaks,
class index and overlap length recorded per peak.

| Class | Features | Feature bp | Covered bp | Fraction | Covered features |
| --- | --- | --- | --- | --- | --- |
| promoter | 29,879 | 33,532,013 | 8,641,127 | 0.257698 | 13,910 |
| utr5 | 23,580 | 439,521,297 | 14,196,925 | 0.032301 | 14,544 |
| cds | 18,764 | 1,013,121,551 | 21,447,983 | 0.021170 | 12,000 |
| utr3 | 23,547 | 232,996,937 | 5,252,568 | 0.022544 | 4,522 |
| exon | 242,251 | 88,190,761 | 6,212,941 | 0.070449 | 24,706 |
| intron | 182,012 | 1,302,227,186 | 28,230,794 | 0.021679 | 31,004 |

Jaccard, rep1 vs IDR: intersection 38,126,042 bp, union 54,681,989 bp,
Jaccard 0.6972321727360722; 123,851 IDR peaks overlap rep1 (0.707052) and
105,924 rep1 peaks overlap IDR (0.980470).

### Oracles (bedtools 2.31.1)

| Quantity | Operator | bedtools | Difference |
| --- | --- | --- | --- |
| annotation class (155,153) | priority sweep | intersect + merge, same priority | 0 mismatches |
| annotation overlap bp | per-peak overlap | intersect, same sweep | 0 mismatches |
| coverage bp, 6 classes | per-class sweep | `bedtools coverage` | exact |
| coverage features / covered features | per-class rows | same | exact |
| Jaccard intersection | 38,126,042 | 38,126,042 | 0 |
| Jaccard union | 54,681,989 | 54,681,989 | 0 |
| Jaccard | 0.6972321727 | 0.697232 | print rounding only |

### Three platforms

| Platform | Elapsed | annotate | coverage | jaccard |
| --- | --- | --- | --- | --- |
| WSL (Ubuntu 24.04) | 71.491 s | 1.956 | 68.949 | 0.489 |
| srv (Slurm login) | 135.495 s | 3.978 | 130.338 | 0.966 |
| Windows (py 3.12) | 83.977 s | 2.212 | 81.094 | 0.543 |

All three exports are byte-identical across platforms:
`interval_annotate.csv` 3,233,068 B `3482ba02fb1020a5c88f5b62d0d890c0`,
`interval_coverage.csv` 470 B `1061f015a9920de02f6bb94f00f59111`,
`interval_jaccard.csv` 285 B `7666007bcaddafc6879f28dfac5cbb37`.

### Limits

- Primary chromosomes only (chr1-22, X, Y); alternate contigs are dropped.
- Coverage uses merged class intervals, so overlapping transcripts of one class
  count once.
- Annotation assigns the first class in priority order and does not split a
  peak across classes.
- Jaccard uses merged intervals and ignores peak confidence and multi-mapping.

## Batch 13 — PBMC3k marker genes (single-cell differential expression)

Route `pbmc_markers` on the 10x PBMC3k subset already used by the trajectory
route: 1,200 cells, 300 highly variable genes, 13 Leiden clusters. Three new
operators compare every cluster against the rest and describe marker
specificity:

| Operator | Inputs | Output |
| --- | --- | --- |
| `sc_rank_genes` | expression `[cell,gene]`, clusters `[cell,cluster]` | `[test,statistic]`, 8 columns, top 50 per cluster |
| `sc_marker_specificity` | expression, clusters | `[gene,statistic]`, tau, top cluster, detection |
| `sc_cluster_profile` | expression, clusters | `[cluster_gene,statistic]`, mean and detection |

### Data

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `input/expression.csv` | 2,542,469 | `fb411e375814117824bf3a1d0653f674549990ce59bb357f3e21593e17810292` |
| `input/clusters.csv` | 23,095 | `758437a38f1c02cb84a440b5ea43f4aac4aedd0baccce08d4d8195dbda859ece` |

Inputs are log-normalised (scale factor 10,000, log1p) and are not shipped with
the operator library.

### Results

The route completes six steps and writes three CSV exports: 650 cluster-gene
tests (13 x top 50), 300 gene specificity rows and 3,900 cluster-gene profile
rows. `GP9` (cluster 11), `RP11-211G3.2` and `TRPM4` (cluster 10), `ARVCF`
(cluster 10) and `CLDN5` (cluster 11) reach tau 1.0. The maximum tau in the
table is exactly 1.0 after the degenerate-gene fix described below.

### Oracles

SciPy 1.16 `mannwhitneyu(method="asymptotic", use_continuity=False)`,
statsmodels BH and direct pandas group means recompute every statistic from the
same inputs:

| Check | Rows | Max abs difference |
| --- | ---: | ---: |
| Wilcoxon p-value | 650 | 1.67e-16 |
| BH adjusted p | 650 | 0.0 |
| log2 fold change | 650 | 3.55e-15 |
| Cluster/rest means | 650 | 1.78e-15 |
| Tau specificity | 300 | 1.11e-16 |
| Top cluster | 300 | 0 mismatches |
| Detection fraction | 300 | 9.71e-17 |
| Profile mean | 3,900 | 4.44e-16 |
| Profile detection | 3,900 | 9.71e-17 |

### Three platforms

| Platform | Steps | Time | `sc_rank_genes.csv` | Marker CSV | Profile CSV |
| --- | ---: | ---: | --- | --- | --- |
| WSL (NumPy 2.1.3) | 6/6 | 0.783 s | 95,749 B `38193627…` | 25,109 B `cd7c5e95…` | 166,576 B `79199ee5…` |
| srv (NumPy 2.4.6) | 6/6 | 1.911 s | 95,748 B `21e6d6f1…` | 25,109 B `cd7c5e95…` | 166,576 B `79199ee5…` |
| Windows (NumPy 2.5.4) | 6/6 | 0.811 s | 95,702 B `2579e0ce…` | 25,109 B `cd7c5e95…` | 166,576 B `79199ee5…` |

Marker and profile exports are byte-identical on all three platforms. The rank
export differs only in floating-point text formatting: column-wise maximum
absolute differences are 0.0 between WSL and srv, and at most 2.22e-16 for
`log2fc`/`adjusted_p` and 1.11e-16 for `p_value` between WSL and Windows.

### Defect found and fixed

The first run reported tau 1.0833 for `RP1-28O10.1`, a gene with no detected
expression in any cluster. With `peaks = 0` every scaled value was 0, so the
formula produced `k / (k - 1)` instead of a bounded specificity. `tau` is now
set to 0 when a gene has no positive cluster mean, and
`test_marker_specificity_zero_gene_has_zero_tau` covers the case (11 tests
pass). The oracle applies the same documented convention. Fix commit
`16e50fa6`; operator commit `30e52c0f`.

### Limitations

Wilcoxon uses the asymptotic normal approximation without continuity
correction; the route covers 300 HVG rather than the full transcriptome; tau is
defined as 0 for genes with no detected expression; cluster labels are numeric
codes from the companion route.

## Batch 14 — E. coli gene-level counts (`ecoli_gene_counts`)

Operators added: `bam_gene_counts`, `counts_normalize`, `bam_gene_bias`
(commit `bf4ee08e`). Registry after the batch: **766 operators / 104 readers /
7 packages / 38 routes**, `errors []`.

### Data

| Input | Size | SHA256 | Source |
| --- | --- | --- | --- |
| `input/ecoli.sorted.bam` | 19,134,169 B | `79e4140a…` | B3 route: `bwa mem` of ENA SRR001666 200k pairs, coordinate sorted + indexed |
| `input/ecoli.gff` | 2,314,238 B | `68d25735ccde6d37af68613dca57a588ae69423f0ecee99b0f29d596eff7accb` | NCBI `GCF_000005845.2_ASM584v2_genomic.gff.gz` (9,531 lines, 4,506 genes with `locus_tag`) |

### Route (6 steps)

`bam_gene_counts` (BAM + GFF) → CSV; `counts_normalize` (counts) → CSV;
`bam_gene_bias` (BAM + GFF) → CSV. Parameters: `min_mapq 30`,
`feature_type gene`, `id_attribute locus_tag`, `bins 5`.

### Results

- 4,506 genes, **328,624** counted alignments.
- `b0001`: counts 10, length 66, CPM 30.429914, TPM 397.275958,
  FPKM 461.059300; bias 5' 0.227273, 3' 0.303030, ratio 0.75.
- Three-platform runtime: WSL 2.0314 s (counts 0.941, bias 1.062); srv
  5.263 s (counts 2.331, bias 2.843); Windows 2.447 s (counts 1.137,
  bias 1.271).

### Oracles

| Comparison | Method | Result |
| --- | --- | --- |
| counts | `bedtools multicov` on `samtools view -q 30 -F 0xB04` filtered BAM | 4,506/4,506 genes, **0 mismatches**, total 328,624 |
| TPM / FPKM / CPM | recomputed from counts and length | **max abs diff 0.0** |
| 5'/3' density ratio | independent `samtools view` CIGAR/midpoint parser, same 5-bin rule | **max abs diff 0.0** (4,506 genes) |

### Defect found by the oracle

The first version passed GFF `start` (1-based) straight into the 0-based
overlap test, so every feature was shifted by one base and its reported length
was one base short (b0001 read 65 instead of 66). Counts were 388 lower than
`bedtools multicov` (328,236 vs 328,624, 371 genes affected) and the bias
ratio differed by up to 2.0. Converting `start - 1` fixed all three outputs
and the oracle then matched exactly. This is the value of the independent
`bedtools` comparison: the unit tests alone accepted the off-by-one.

### Byte identity

| File | Size | MD5 (WSL = srv = Windows) |
| --- | --- | --- |
| `bam_gene_counts.csv` | 165,533 B | `2a1e39cbd50100136ce59df9114de8ad` |
| `counts_normalize.csv` | 279,099 B | `741c7588cefe7c401343d7a7e1e382c1` |
| `bam_gene_bias.csv` | 267,533 B | `4ff440340ccb18781a713bccc4e7ef94` |

### Limitations

Primary alignments only (secondary/supplementary/qcfail excluded); reads are
counted once per overlapped gene; duplicate-flagged reads are kept to match
`bedtools multicov` defaults; `count_pairs` uses read 1 only. The bias metric
is a 5'/3' edge-window density ratio, not a full gene-body coverage model.

## Batch 15 - genome k-mer comparison (K-12 vs O157:H7)

**Operators:** `genome_kmer_spectrum`, `genome_kmer_similarity`,
`genome_mash_distance` (category Genome).
**Route:** `genome_kmer_comparison` (builtin, 6 steps).

### Data

| Source | File | Bytes | SHA256 |
| --- | --- | --- | --- |
| *E. coli* K-12 MG1655, `GCF_000005845.2` | `input/ecoli.fasta` | 4,699,745 | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |
| *E. coli* O157:H7 Sakai, `GCF_000008865.2` | `input/o157.fna` | 5,664,775 | `71c2e5c364293c9ba36fc2c7acbcaa75cd6884295fe06260ba198826a8b1ddd3` |

Both assemblies are public NCBI RefSeq downloads; O157 includes its plasmids,
all records are canonicalised into 21-mers.

### Route and results

| Step | Result |
| --- | --- |
| `genome_kmer_spectrum` (k=21, max 50) | 4,543,891 distinct canonical 21-mers, 4,641,632 occurrences, 37 observed multiplicities, 15 k-mers in the `50+` bucket |
| `genome_kmer_similarity` (k=21) | K-12 4,543,891 unique, O157 5,302,382 unique, shared 3,064,483, union 6,781,790, Jaccard 0.4518693442291784 |
| `genome_mash_distance` (k=21) | distance 0.0225746167074651, ANI 0.9774253832925349, shared 3,064,483 |

No step failed; WSL total 5.8886 s (1.317 / 2.282 / 2.285 s).

### Oracles

| Oracle | Version | Agreement |
| --- | --- | --- |
| jellyfish spectrum (`jellyfish count -m 21 -C`, `histo`) | 2.3.1 | dense 1..51 buckets: `n_kmers` max abs diff 0.0, fraction 9.56e-17, total 4,543,891 both, overflow bucket 15 both |
| jellyfish set intersection (`dump -c`) | 2.3.1 | shared 3,064,483, union 6,781,790, Jaccard 0.4518693442291784 (0.0 diff) |
| Mash formula on exact Jaccard | published formula | distance 0.0225746167074651 (0.0 diff), ANI diff 1.1e-16 |
| `mash dist -k 21 -s 1000000` | 2.3 | 0.0225412, delta 3.34e-5; MinHash sketch estimate, recorded as approximation only |

### Three-platform check

| Platform | Time | Notes |
| --- | --- | --- |
| WSL (Ubuntu 24.04, numpy 2.1.3) | 5.8886 s | reference run |
| srv (Linux, python 3.11, numpy 2.4.6) | 33.6087 s | 4.6 / 14.0 / 15.0 s per operator |
| Windows (py 3.12) | 17.7794 s | 1.8 / 7.9 / 8.1 s per operator |

All three exports are byte-identical across platforms:

| File | Bytes | MD5 |
| --- | --- | --- |
| `kmer_spectrum.csv` | 1,180 | `246461869187019e6541ed46c45d4b0f` |
| `kmer_similarity.csv` | 208 | `6ce3108f075d99d8ddcc14140fb5578d` |
| `mash_distance.csv` | 172 | `1cf37646e132cce03829650e2da0315e` |

Registry after the batch: **769 operators / 104 readers / 7 packages / 39
routes**, errors 0, warnings 113 (all pre-existing).

### Limits

- The spectrum table is sparse plus a `50+` overflow bucket; dense histogram
  comparisons must fill missing multiplicities with zero.
- `k` is limited to 3-31 by the 2-bit encoding; windows containing non-ACGT
  characters are skipped.
- Mash distance and ANI are alignment-free and computed from the exact Jaccard
  index, so they are deliberately slightly different from sketch-based
  `mash dist` output (delta 3.34e-5 here).
- k-mers are canonicalised, so strand-specific or CpG-aware analyses are out of
  scope.

## Batch 16 — assembly contiguity and gap quality control

**Commit:** `34a43879` (operators + route) — three-platform runs below.
**Operators:** `assembly_contig_stats`, `assembly_contiguity`, `assembly_gap_stats`
(3 new; library registry **772 operators / 104 readers / 7 packages / 40 routes**,
errors 0, warnings 113).

### Data

| Source | Content | Size (B) | SHA-256 |
| --- | --- | --- | --- |
| `input/genome.fna` | *S. cerevisiae* S288C, GCF_000146045.2, 17 records (16 chromosomes + mitochondrion) | 12,310,392 | `fe42735d3e6242f8c40b457a232940e34ef15eb4502717e54a34ed118face4c1` |
| `input/ecoli.fasta` | *E. coli* K-12 MG1655, GCF_000005845.2, 1 record | 4,699,745 | `53bb6a51b6e92139ced1e38f74b7938781027c52200922ff03718c2237d23bb4` |

Both are public RefSeq assemblies already used by earlier batches (the yeast
genome was fetched for batch 8; the E. coli genome is the batch 3 reference).
The E. coli single-contig input is the zero-gap negative control.

### Route `assembly_qc` (10 steps)

`assembly_contig_stats` (yeast) → export → `assembly_contiguity` → export →
`assembly_gap_stats` (yeast) → export → the same two operators on E. coli →
export. `assembly_contig_stats` emits per-contig `length`, `gc_fraction`,
`n_fraction`, `n_runs`; `assembly_contiguity` reduces that table to
`n_contigs`, `total_bp`, min/mean/median/max length, `n50`/`l50`, `n90`/`l90`,
`auN` and length-weighted GC; `assembly_gap_stats` counts `N` runs per contig
and reports genome-wide gap totals.

### Results

| Metric | Yeast S288C | E. coli K-12 |
| --- | --- | --- |
| Contigs | 17 | 1 |
| Total bp | 12,157,105 | 4,641,652 |
| Min / median / max length | 85,779 / 745,751 / 1,531,933 | 4,641,652 / 4,641,652 / 4,641,652 |
| N50 / L50 | 924,431 / 6 | 4,641,652 / 1 |
| N90 / L90 | 439,888 / 13 | 4,641,652 / 1 |
| auN | 904,609.4998252462 | 4,641,652.0 |
| GC fraction | 0.3814786497 | 0.5079070986 |
| Gap runs / gap bp | 0 / 0 | 0 / 0 |

### Oracles

| Oracle | Version | Compared | Result |
| --- | --- | --- | --- |
| `seqkit stats -a` | 2.9.0 | num_seqs, sum_len, min/avg/max, Q1/Q2/Q3, N50, N50_num, GC%, sum_n | identical (17/12,157,105/85,779/715,123.8/1,531,933/439,888/745,751/948,066/924,431/6/38.15%/0; E. coli 1/4,641,652/…/50.79%/0) |
| Biopython `SeqIO` + independent N50 and `N+` regex gap code | 1.86 | per-contig lengths, n50/l50, auN, weighted GC, gap runs and gap bp | max abs diff **0.0** for every value; gap counts equal; `workdir/b16_oracle.json` `passed: true` |

The Biopython script recomputes N50 with its own cumulative loop and finds gaps
with `re.finditer("N+", …)`; it does not import the operator helpers, so the two
implementations are independent code paths. `seqkit` is a third, external
implementation.

### Three platforms

| Platform | Steps | Total (s) | Notes |
| --- | --- | --- | --- |
| WSL (Python 3.12, numpy 2.3) | 10/10 | 0.7903 | contig stats 0.296 s, gaps 0.269 s (yeast); 0.116 / 0.103 s (E. coli) |
| srv (Python 3.11, venv 3.0.1) | 10/10 | 1.4888 | contig stats 0.554 s, gaps 0.491 s (yeast) |
| Windows (py 3.12) | 10/10 | 1.1493 | contig stats 0.251 s, gaps 0.395 s (yeast); registry 772/104/7/40, errors 0 |

All five exported CSVs are **byte-identical** across the three platforms:

| File | MD5 |
| --- | --- |
| `yeast_contiguity.csv` | `b34c57050b4eef746220f984763baa1d` |
| `yeast_contig_stats.csv` | `9bf57f9c2da54eaec27622941b447a53` |
| `yeast_gaps.csv` | `b30e8320f229f67b7c73b5923c1401a0` |
| `ecoli_contig_stats.csv` | `72b6a0312a539d44bd058f0076bf4560` |
| `ecoli_gaps.csv` | `e5d4898840a713e9a0308c23c5330c22` |

### Notes and limitations

- No product defect was found in this batch; the only code change during
  bring-up was making `estimate_memory` tolerate an empty `inputs` list (the
  planner passes `[]` in unit tests), covered by
  `tests/test_extension378.py::test_estimate_memory_contract`.
- `assembly_contiguity` requires a `length` column in the contig table and
  rejects a table without it; `gc_fraction` is optional and length-weighted.
- N/L statistics count `N` runs at full contig length; gaps are reported
  separately and are not subtracted from `total_bp`.
- `auN` is contig-length based and is not assembly-graph aware.
- Both inputs are finished reference assemblies, so the gap operator is
  exercised only on its zero-gap path here; the >0 gap path is covered by unit
  tests with synthetic `N` runs.
- QUAST is not used as an oracle in this batch: it is an external tool wrapper
  (`assembly_stats`) already covered by packaging tests; `seqkit` plus the
  independent Biopython implementation provide the two required oracles.

## Batch 17 — SSU rRNA phylogeny (distance matrix, neighbour joining, tree distance)

**Operators:** `phylo_distance_matrix`, `phylo_neighbor_joining`,
`phylo_tree_distance` (3 new). Route: `ssu_phylogeny`.

| Item | Value |
| --- | --- |
| Family | Rfam RF00177 (SSU_rRNA_bacteria) seed alignment |
| Source | <https://rfam.org/family/RF00177/alignment> |
| Stockholm | 477,373 B, SHA-256 `efe8d15fab12034e79aa5c8599b1018de2ac8a98257ec0df94a1347112177276` |
| Alignment | 1,980 columns, 99 seed sequences |
| Route input | 24 taxa, `input/ssu_aligned.fasta`, 48,899 B, MD5 `d63358e9c42a1a7566666058b9d3ddda` |
| Model | complete deletion (1,396 columns), JC69 and p distances |

The route runs 11 steps: JC69 matrix, NJ tree (Newick + node table),
p-distance matrix, NJ tree, then a tree comparison between the two NJ trees.

### Results (WSL)

| Output | Value |
| --- | --- |
| `ssu_distance_jc69.csv` | 24 x 24 symmetric matrix, 12,023 B |
| `ssu_nj_jc69.nwk` | 24-tip rooted tree, 1,247 B |
| `ssu_nj_p.nwk` | 24-tip rooted tree, 1,257 B |
| `ssu_tree_distance.csv` | `rf=14`, `max_rf=42`, `normalized_rf=0.333333`, `shared_splits=14`, `splits=21/21`, `branch_score=0.024637590466330808`, `identical=0` |

### Oracles

| Oracle | Version | Check | Result |
| --- | --- | --- | --- |
| Biopython `DistanceCalculator("identity")` | 1.88 | p-distance matrix | max abs **5.55e-17** |
| Biopython `DistanceTreeConstructor().nj` | 1.88 | unrooted splits | RF **0**, 21/21 shared |
| Biopython NJ branch lengths | 1.88 | split lengths (root edge summed) | max abs **4.06e-12** |
| R `ape` `dist.dna(model="JC69")` | 5.8.1 | JC69 matrix | max abs **0** |
| R `ape` `nj` + `dist.topo(PH85)` | 5.8.1 | unrooted topology | RF **0** |
| R `ape` `cophenetic` | 5.8.1 | tip-to-tip distances | max abs **9.17e-11** |

Biopython 1.88 dropped the `jc69` model from `DistanceCalculator`, so it
oracles p-distances and neighbour joining; JC69 is checked with R `ape`.
Oracle scripts: `workdir/b17_oracle.py`, `workdir/b17_oracle.R`,
results in `workdir/b17_oracle.json`.

### Defect found and fixed

`phylo_distance_matrix` narrowed the distance matrix to float32
(`matrix.astype(np.float32)`), shifting p-distances by up to 1.5e-8 and NJ
branch lengths by 2.9e-4. The matrix is now float64;
`tests/test_extension379.py::test_distance_matrix_operator_keeps_float64_precision`
pins the 361/1396 p-distance exactly (it would have failed before the fix).

### Three platforms

| Platform | Steps | Time | Notes |
| --- | --- | --- | --- |
| WSL (Python 3.12, Biopython 1.88) | 11/11 | 1.10 s | oracle host |
| srv (Python 3.11) | 11/11 | 0.95 s | real cluster |
| Windows (py -3.12) | 11/11 | 0.42 s | `registry check` 775/104/7/41, errors 0 |

MD5 of the six exports is identical on all three platforms, except the two
Newick files on Windows, which use CRLF line endings; after stripping `\r`
their MD5 is identical (`9516b49d...`, `e57ddcef...`).

### Limitations

- The alignment is the curated Rfam seed alignment; the route does not align
  sequences de novo.
- Neighbour joining, not maximum likelihood; no bootstrap support.
- 24 of 99 seed sequences are sampled by equal stride to keep the route small.
- `U` is treated as a base; JC69 uses only the mismatch fraction.

## Batch 18 — MSA analysis route (Pfam PF00069 + Rfam RF00177)

Four operators summarise and clean an existing alignment without calling an
aligner: `msa_column_stats`, `msa_consensus`, `msa_identity_matrix` and
`msa_trim`. The route key is `msa_analysis`.

### Data

| Source | File | Size | SHA-256 |
| --- | --- | --- | --- |
| Pfam PF00069 seed | `input/pf00069_aligned.fasta` | 16,491 B | `b6e130f45be1e63a1c6bda22fcdce7641781a1b8a2dbbd056a55df344f95228f` |
| Rfam RF00177 subset | `input/ssu_aligned.fasta` | 48,899 B | `6df770ce70b0e6e6dac180266929c5f61d2929cb93c846fc4809d18945772c44` |

PF00069 was fetched as the raw seed Stockholm file from the InterPro API
(`https://www.ebi.ac.uk/interpro/wwwapi/entry/pfam/PF00069/?annotation=alignment:seed`,
36,601 B, gzip encoded) and converted to FASTA with gaps preserved: 37
sequences x 419 columns. The RNA alignment is the 24-sequence Rfam RF00177
subset already used by the phylogeny route (alignment length 1,980).

`FastaReader` decodes `-` as an unknown base (N), so the operators read
`info["sequences"]` through `_annotation_utils.fasta_sequences`; decoding the
numeric codes would silently erase every gap.

### Steps

12 steps: protein column statistics -> CSV, consensus -> FASTA, identity
matrix -> CSV, trim -> FASTA; then RNA column statistics -> CSV and consensus
-> FASTA.

### Results

| Platform | Steps | total_elapsed | managed_peak_bytes |
| --- | --- | --- | --- |
| WSL (3.12) | 12 | 0.0471 s | 699,530 |
| Windows (3.12) | 12 | 0.0747 s | 699,512 |
| srv (3.11) | 12 | 0.2078 s | 732,204 |

| Output | Bytes | MD5 (WSL = Windows) |
| --- | --- | --- |
| `msa_columns_pf00069.csv` | 27,155 | `fb4b7dada33209ea3b11723a8e95d899` |
| `msa_columns_rfam.csv` | 86,775 | `9a093e24f7f49f12ea635fb18141b065` |
| `msa_consensus_pf00069.fasta` | 436 | `c7ac6457c1fafe642df9a14c82018230` |
| `msa_consensus_rfam.fasta` | 2,016 | `8a0724cc3c95b76ea156054583a70d8c` |
| `msa_identity_pf00069.csv` | 26,756 | `7b17509334b1a8743d31a07da1e462a6` |
| `msa_trimmed_pf00069.fasta` | 10,016 | `58029201417399d72ef478f6920da845` |

The protein consensus is 419 characters, 309 of them `X` (gap > 0.5 or major
fraction < 0.4); the RNA consensus is 1,980 characters, 526 of them `N`.
Trimming keeps 246 of 419 protein columns and all 37 sequences.

srv writes the two column-statistics CSVs with different text (113 and 143
rows differ in the last decimal) because `math.log2` comes from a different
libm; the numeric difference is at most **1.33e-15** (entropy) and
**3.33e-16** (conservation), and gap fraction and major fraction are identical.
The other four outputs are byte-identical on all three platforms.

### Oracles

| Oracle | Implementation | Result |
| --- | --- | --- |
| Pure Python | `workdir/b18_oracle.py`, own FASTA/CSV parsing, no Biopython | gap/entropy/conservation/major max abs **0.0** on both alignments; consensus identical; identity max abs **0.0**; trimmed alignment identical (246 columns, 37 rows) |
| Base R 4.3.3 | `workdir/b18_oracle.R`, no R packages | same four statistics **0.0** on both alignments; consensus identical (309 `X`, 526 `N`); identity max abs **0.0** |

### Fixes

- `_msa_utils` DNA/RNA alphabets now accept IUPAC ambiguity codes
  (`ACGTRYSWKMBDHVN` / `ACGURYSWKMBDHVN`); the Rfam seed alignment contains
  `M`, `R`, `W`, `Y` and `U`.
- `msa_trim` declares its FASTA output as `kind: file, numeric: false, ndim: 0`
  with `representation.const: fasta`; a plain tensor contract made the runner
  reject the artifact with "needs form data; needs a numeric tensor".
- Trim rows are filtered by the fraction of residues over the retained columns,
  not over the original width.

### Limitations

- The operators never align sequences; input must already be aligned.
- Trimming removes whole columns only.
- Consensus thresholds are per-run parameters, not biological recommendations.
- Identity counts only columns where both sequences carry a residue; short
  overlaps can give high identity.
- The alphabet is inferred once per alignment; mixed nucleotide/protein input is
  rejected.
