# Public-data route combinations

These five examples combine the registered Readers and operators into complete
analysis workflows. The bundled inputs are public-data subsets, not synthetic
fixtures. Each directory contains `task.yaml` (topology and execution settings),
`parameters.json` (frozen Reader and operator argument values), `input/`, and the
upstream author's `ANALYSIS.md`.

| Example | Input | Workflow | Steps |
|---|---|---|---:|
| `refseq_cds_sequence_features` | Six human RefSeq CDS records in FASTA | Sequence statistics, translation, protein properties, correlations and codon usage | 11 |
| `thousand_genomes_chr22_population` | 1000 Genomes chr22 VCF subset and sample metadata | Genotype QC, PCA, Hudson FST and relationship matrix | 13 |
| `leukemia_all_aml_expression` | GSEA Leukemia GCT, 48 ALL/AML samples | PCA, Mann–Whitney tests, BH correction, heatmap and random forest | 11 |
| `pbmc3k_single_cell_atlas` | Processed PBMC3k H5AD and cell annotations | PCA/UMAP, annotated cell-type summaries, marker heatmap and random forest | 12 |
| `qiime_moving_pictures_microbiome` | QIIME moving-pictures BIOM and derived sample groups | Diversity, Bray–Curtis PCoA, PERMANOVA and taxa heatmap | 13 |

## Run or validate

Copy an example directory into a writable workspace. Keep its topology, parameter
JSON and inputs together. From a Operon checkout, run:

```text
python scripts/run.py <example-directory> --check
python scripts/run.py <example-directory>
```

`--check` validates paths, selected Reader IDs, parameter schemas and graph
contracts using the installed index or the task's frozen plugin lock. It does not
parse input payloads, load scientific implementations or execute operators. A
successful preflight does not prove that optional runtime dependencies are present
or that a scientific analysis is appropriate for the supplied data.

Memory management is enabled in these examples. Normal execution uses the startup
memory snapshot and automatic spill handling. A test or a smaller machine can set
an explicit managed budget without editing the saved workflow:

```text
python scripts/run.py <example-directory> --memory-mb 512
```

Outputs are saved under the copied directory's `output/`: per-step reports,
structured events, run summaries, managed-memory reports, and figures. Plotting
steps write PNG previews plus PDF and SVG originals. Managed runs place these
files inside `output/runs/<run-id>/figures/`; use the saved run reports or the
application result links to open them.

Each source selects a registered Reader explicitly through `source.reader`.
Reader arguments and operator values are frozen in `parameters.json`, so later
changes to library defaults do not change the example. Edit that JSON to vary an
analysis. Keep each entry's `name` and `inputs` aligned with the topology.

## Data provenance and interpretation

- **RefSeq CDS:** NCBI RefSeq records for TP53, BRCA1, BRCA2, EGFR, KRAS and PTEN.
  Accessions and protein references are recorded in
  `refseq_cds_sequence_features/input/refseq_cds_sources.tsv`. The FASTA labels were
  simplified for display; this is not an experiment on cancer phenotypes.
  [RefSeq reference](https://doi.org/10.1093/nar/gkv1189).
- **1000 Genomes:** Phase 3, GRCh37 chr22:16,000,000–16,200,000; 20 samples from each
  of five super-populations. This small interval cannot support genome-wide
  population or relatedness conclusions.
  [Original release](https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/).
- **Leukemia:** the GSEA ALL/AML example, with 24 samples per group. Expression
  values are signed measurements rather than raw counts; fold-change fields from
  count-oriented routines may be undefined and should not be interpreted. The
  example uses rank tests and adjusted p-values, with no independent clinical
  validation.
  [GSEA datasets](https://www.gsea-msigdb.org/gsea/datasets.jsp),
  [Armstrong et al.](https://doi.org/10.1038/ng809).
- **PBMC3k:** a processed Scanpy version of 10x PBMC3k, containing 2,638 cells and
  1,838 genes. It is already transformed and is not normalized again here. The cell
  labels are upstream annotations, not independent biological ground truth.
  [10x dataset](https://www.10xgenomics.com/datasets/3-k-pbm-cs-from-a-healthy-donor-1-standard-1-1-0),
  [Scanpy reference](https://doi.org/10.1186/s13059-017-1382-0).
- **QIIME moving pictures:** 34 samples and 770 taxa before example filtering.
  `subject` is derived from the sample ID prefix, not a body-site or clinical
  label. Repeated measurements and other covariates require a study-specific
  statistical design; this example does not establish ecological significance.
  [QIIME tutorial inputs](https://docs.qiime2.org/2024.10/data/tutorials/moving-pictures/),
  [study reference](https://doi.org/10.1186/gb-2011-12-5-r50).

The original analysis documents are retained as provenance. Their reported values
and interpretations belong to the upstream author's run. The unified-application
acceptance tests assess execution, frozen parameters, managed memory and saved
figure outputs, not biological significance. See [VALIDATION.md](VALIDATION.md)
for the current integration evidence.
