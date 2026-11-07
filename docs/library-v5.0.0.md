# Operon Operator Library 5.0.0 — library reference

This page describes the operator library that ships as Operon Operator Library
v5.0.0. It is generated from the same static registry that Studio 3.0.2 loads.

## Version and compatibility

| Item | Value |
| --- | --- |
| Library version | 5.0.0 |
| Minimum application | 3.0.2 |
| Built and verified against | 3.0.2 |
| SDK | 3.7.0 (operator protocol v3 declarations) |
| Operators | 867 |
| Readers | 108 |
| Packages | 7 |
| Builtin routes | 72 |

The library keeps literal operator protocol v3 declarations. SDK 3.5, 3.6 and
3.7 capabilities are additive and optional; 5.0.0 does not advertise explicit
`data_formats` because generic operators such as `export_results` cannot state
closed port types yet. The rationale and the reverted migration experiment are
recorded in `docs/verification/operon-5.0.0-compatibility.md`.

## Operators by category

| Category | Operators |
| --- | --- |
| Statistics | 265 |
| Machine Learning | 230 |
| Omics | 83 |
| Structure | 56 |
| Genome | 54 |
| Sequence | 39 |
| Quality Control | 25 |
| Data | 16 |
| 数据整理 | 16 |
| analysis | 13 |
| 可视化 | 13 |
| 统计分析 | 12 |
| Proteomics | 9 |
| Phylogenetics | 6 |
| data | 6 |
| Causal Inference | 4 |
| 质量控制 | 4 |
| Docking | 3 |
| Metabolism | 3 |
| Network | 3 |
| data preparation | 2 |
| Analysis | 1 |
| Antibody | 1 |
| Ligand | 1 |
| Visualization | 1 |
| visualization | 1 |

The full catalog with titles and descriptions is available from the Studio
operator browser and from `library/seed/operator_index.json`.

## Packages

| Package | Title | Operators |
| --- | --- | --- |
| `operon-readers` | Data readers | 107 |
| `operon-core` | Core transforms | 789 |
| `operon-genetics` | Genetics and statistics | 21 |
| `operon-expression` | Expression analysis | 13 |
| `operon-plots` | Visualization | 12 |
| `operon-microbiome` | operon-microbiome | 26 |
| `operon-hic` | operon-hic | 7 |

## Readers

| Category | Readers |
| --- | --- |
| Data | 89 |
| None | 15 |
| Hi-C | 4 |

Readers are listed with ids in `library/seed/reader_index.json`. File readers
(BAM, VCF, FASTA, chain, pairs, matrix, BED and tabular formats) produce native
file artifacts; analysis readers produce typed Forms.

## Builtin routes

Every route below is validated by `operon registry build --scope routes` and
is importable from Studio (individually as `.operon.zip` or as one
`Operon-Routes-v5.0.0.zip` archive).

| Route | Title |
| --- | --- |
| `assembly_ngx_qc` | Assembly completeness (NGx/auN) |
| `assembly_qc` |  |
| `atac_peak_calling` |  |
| `atac_qc` |  |
| `b9_ml` |  |
| `bam_alignment_qc` | BAM alignment quality control |
| `bgen_qc` |  |
| `codon_design` | Codon optimisation and QC |
| `codon_usage_bias` |  |
| `ecoli_annotation` |  |
| `ecoli_gene_counts` |  |
| `ecoli_resequencing` |  |
| `fastq_composition_qc` | FASTQ duplication, over-representation and GC QC |
| `fba_flux_balance` |  |
| `genome_comparison` |  |
| `genome_kmer_comparison` |  |
| `genotype_structure` |  |
| `gm12878_interval_annotation` |  |
| `go_enrichment` |  |
| `go_semantic_similarity` |  |
| `golub_coexpression` |  |
| `gtf_annotation` |  |
| `gwas` |  |
| `gwas_association` | GWAS association on chr22 |
| `gwas_meta_prs` |  |
| `hic_bam` |  |
| `hic_fastq` |  |
| `hic_pair_qc` |  |
| `hic_pairs` |  |
| `interval_analysis` |  |
| `lalonde_psm` |  |
| `ld_analysis` |  |
| `liftover_intervals` | liftOver intervals and variants |
| `microbiome` |  |
| `microbiome_diff` |  |
| `ml_classification` |  |
| `ml_regression` |  |
| `ml_validation` |  |
| `msa_analysis` |  |
| `multi_omics` |  |
| `pbmc_markers` |  |
| `pbmc_trajectory` |  |
| `peptide_msms` |  |
| `phylo_bootstrap_support` |  |
| `phylo_comparative` |  |
| `ppi_network_analysis` | STRING CRP network analysis |
| `primer_design_qc` |  |
| `proteome_properties` |  |
| `proteomics_de` |  |
| `proteomics_limma` |  |
| `proteomics_qc` |  |
| `prs_harmonize_qc` |  |
| `pwm_scan_chr22` |  |
| `read_preprocessing` |  |
| `restriction_digest` |  |
| `rna_structure_compare` |  |
| `rnaseq_de` |  |
| `rnaseq_de_enrichment` |  |
| `rnaseq_ssgsea` |  |
| `sequence_features` |  |
| `sequencing_qc` |  |
| `single_cell` |  |
| `single_cell_batch` |  |
| `single_cell_loom` |  |
| `ssu_phylogeny` |  |
| `structure_validation` |  |
| `survival` |  |
| `tree_manipulation` |  |
| `variant_annotation` |  |
| `variant_qc_concordance` |  |
| `vcf_normalization` |  |
| `vcf_sample_qc` | VCF sample and site quality control |

## Verification

- Static registry: 867 operators, 108 readers, 7 packages, 72 routes, 0 errors.
- Release verification: application 3.0.2 unchanged after install, frozen route
  parameters preserved, idempotent install and worker streaming pass.
- Route evidence: `docs/verification/routes-4.x.md` records the real-data runs
  and independent oracles accumulated across the 4.x and 5.0.0 cycles.
- Full test suite result for the release tree is recorded in the release notes.

## Installation

1. Install Operon Studio 3.0.2 (or newer).
2. Download `Operon-Library-v5.0.0-Windows.operon-library.zip` or the Linux package.
3. In Studio open **Operator Library -> Import package** and select the archive.
4. Optionally import `Operon-Routes-v5.0.0.zip` to add the 72 builtin routes.

Legacy `.biopipe-library.zip` bundles remain selectable in the picker, but new
installs should use the `.operon-library.zip` package.
