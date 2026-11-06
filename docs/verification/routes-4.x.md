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
