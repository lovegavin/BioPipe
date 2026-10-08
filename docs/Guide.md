# Guide

This guide walks you through installing BioPipe, preparing input data, running a task, and interpreting the outputs. It assumes no prior knowledge of the framework.

For the exact input format contract, see [input_spec.md](input_spec.md). For the reasoning behind the design, see [architecture.md](architecture.md).

---

## 1. Installation

BioPipe requires Python 3.11 or newer.

### 1.1 Create the environment

The recommended way is Conda:

```bash
git clone https://github.com/lovegavin/BioPipe.git
cd biopipe

conda env create -f environment.yml
conda activate biopipe
```

### 1.2 Manual install

If you prefer pip:

```bash
pip install numpy pandas scipy statsmodels pysam bed-reader matplotlib pyyaml openpyxl
```

### 1.3 Verify

```bash
python -c "from src.pipelines import PIPELINES; print(list(PIPELINES))"
```

Expected output:

```text
['gwas']
```

---

## 2. Prepare your data

BioPipe expects inputs to live inside a task directory:

```text
tasks/
  task_001_myrun_GWAS/
    input/
      genotype.vcf.gz
      phenotype.csv
      covariates.csv        # optional
```

Create the directory and drop the files in:

```bash
mkdir -p tasks/task_001_myrun_GWAS/input
cp /path/to/your/genotype.vcf.gz tasks/task_001_myrun_GWAS/input/
cp /path/to/your/phenotype.csv   tasks/task_001_myrun_GWAS/input/
cp /path/to/your/covariates.csv  tasks/task_001_myrun_GWAS/input/   # optional
```

### 2.1 File names

Input files are identified by convention:

| Role | Accepted names |
|---|---|
| Genotype | `genotype.vcf.gz`, `genotype.vcf`, `genotype.bed` (+ `.bim`, `.fam`) |
| Phenotype | `phenotype.csv`, `phenotype.tsv`, `phenotype.txt`, `phenotype.xlsx`, `phenotype.parquet` |
| Covariates | `covariates.<same extensions>` |

If your files use different names, edit `manifest.yaml` after step 3.1.

### 2.2 Column names

Column names are fixed. See [input_spec.md](input_spec.md) for the exact contract.

**Phenotype** — two columns only:

```text
sample_id,trait_value
```

**Covariates** — first column is `sample_id`, the rest are free:

```text
sample_id,age,sex,batch
```

### 2.3 Sample IDs

Sample IDs must match exactly across genotype, phenotype and covariate files. Alignment is done by string comparison.

---

## 3. Run a task

Three commands. Run them from the repository root.

### 3.1 Generate the manifest

```bash
python scripts/init_task.py --task tasks/task_001_myrun_GWAS
```

This scans `input/`, identifies file roles, and writes `manifest.yaml` inside the task directory.

```text
tasks/task_001_myrun_GWAS/
  manifest.yaml     # generated
```

Open `manifest.yaml` and adjust any parameter you want to change — QC thresholds, PCA toggle, association model, plot selection. The file is commented and intended to be edited.

### 3.2 Validate the manifest

```bash
python scripts/validate_task.py --task tasks/task_001_myrun_GWAS
```

This checks that the manifest is well-formed and that every declared input path exists. No computation is performed.

Expected output:

```text
Manifest OK: tasks/task_001_myrun_GWAS/manifest.yaml
```

### 3.3 Run the pipeline

```bash
python scripts/run.py --task tasks/task_001_myrun_GWAS
```

You should see step-by-step progress:

```text
[INFO] Pipeline start: 11 steps
[INFO] [1/11] load
[vcf] loaded 5000 variants x 150 samples (ploidy=2)
[table] phenotype: 150 samples
[table] covariates: 150 samples x 3 columns
[INFO] [1/11] load done in 0.51s
...
[INFO] Pipeline finished successfully
```

The full log is written to `tasks/task_001_myrun_GWAS/logs/run.log`.

---

## 4. Inspect the outputs

After a successful run, the task directory looks like this:

```text
tasks/task_001_myrun_GWAS/
  input/
  manifest.yaml
  output/
    gwas_result.tsv
    run_metadata.json
    figures/
      manhattan.png
      qq.png
      volcano.png
      forest.png
      maf_distribution.png
      pvalue_histogram.png
      chromosome_density.png
      effect_vs_maf.png
      pca_scatter.png
      pca_scree.png
  processed/
    ld_pruned_snps.txt
    pca_result.tsv
    pca_variance.tsv
    significant_snps.tsv
    independent_significant_snps.tsv
    top_snps.tsv
  logs/
    run.log
```

### 4.1 Primary result — `output/gwas_result.tsv`

Tab-separated. One row per variant.

| Column | Type | Description |
|---|---|---|
| `ID` | str | Variant identifier |
| `CHROM` | str | Chromosome |
| `POS` | int | Position (1-based) |
| `REF` | str | Reference allele |
| `ALT` | str | Effect allele |
| `MAF` | float | Minor allele frequency |
| `BETA` | float | Effect size (per ALT copy) |
| `SE` | float | Standard error |
| `P` | float | P-value |
| `N` | int | Number of samples used for this variant |
| `Q_VALUE` | float | FDR Q-value (only when `correction.method: fdr`) |
| `SIGNIFICANT` | bool | Passes the configured correction |

### 4.2 Run metadata — `output/run_metadata.json`

Records everything needed to reproduce the run:

- Pipeline name and version
- Python version and platform
- Versions of tracked dependencies
- Full manifest
- Per-step timings
- Alignment, sample QC, SNP QC and correction summaries
- Input paths

### 4.3 Figures — `output/figures/`

| Figure | Purpose |
|---|---|
| `manhattan.png` | Genome-wide signal overview |
| `qq.png` | P-value distribution with λGC |
| `volcano.png` | Effect size vs significance |
| `forest.png` | Top-N variants with 95% CI |
| `maf_distribution.png` | Minor allele frequency distribution |
| `pvalue_histogram.png` | P-value histogram vs uniform |
| `chromosome_density.png` | Variant count per chromosome |
| `effect_vs_maf.png` | Effect size vs frequency |
| `pca_scatter.png` | PC1 vs PC2 |
| `pca_scree.png` | Explained variance per component |

### 4.4 Intermediate files — `processed/`

| File | Contents |
|---|---|
| `ld_pruned_snps.txt` | Variant IDs retained after LD pruning (PCA input only) |
| `pca_result.tsv` | Sample × PC matrix |
| `pca_variance.tsv` | Explained variance ratio per PC |
| `significant_snps.tsv` | Variants passing the correction threshold |
| `independent_significant_snps.tsv` | Significant variants after LD clumping |
| `top_snps.tsv` | Top 20 variants by P-value |

---

## 5. Adjusting the manifest

Open `manifest.yaml` to change any parameter. The most common edits:

**Disable PCA**

```yaml
pca:
  enabled: false
```

**Change QC thresholds**

```yaml
qc:
  maf: 0.05
  missing: 0.05
  sample_missing: 0.05
  hwe: 1.0e-6
```

**Switch to standard logistic regression**

```yaml
association:
  binary_model: logit
```

**Use FDR instead of Bonferroni**

```yaml
correction:
  method: fdr
  fdr_threshold: 0.05
```

**Disable plots selectively**

```yaml
plots:
  volcano: false
  forest: false
```

After editing, re-run:

```bash
python scripts/run.py --task tasks/task_001_myrun_GWAS
```

The manifest is the only file you should edit after `init_task.py`. Do not edit `run.py` or any pipeline code to change behaviour.

---

## 6. Common errors

| Error message | Cause | Fix |
|---|---|---|
| `Unrecognized genotype extension: '.vcfq'` | File extension typo | Rename to `.vcf` or `.vcf.gz` |
| `Schema mismatch ... Expected: sample_id, trait_value` | Wrong column names | Rename columns exactly |
| `No common samples` | Sample IDs differ across files | Ensure IDs match |
| `Excel does not support compression` | `.xlsx.gz` | Remove the `.gz` suffix |
| `PLINK component missing` | `.bim` or `.fam` not found | Keep all three files together |
| `Unable to infer ploidy from VCF` | No valid `GT` calls | Check the VCF for `GT` data |
| `Covariates contain missing values` | `NaN` in covariates | Clean the covariate file |
| `Sample missingness filter removed every sample` | Threshold too strict | Raise `qc.sample_missing` |
| `Step 'X' declared form 'Y' but did not register it` | Plugin bug | Report to the maintainer |

Full contract details for inputs: [input_spec.md](input_spec.md).

---

## 7. FAQ

**Why are column names not auto-detected?**

Because guessing is worse than failing. When a reader accepts `id` as a synonym for `sample_id`, and later someone uses `id` to mean something else, the pipeline silently produces wrong results. Fixed names mean predictable failures.

**Why is `.gz` not treated as VCF?**

Because `.csv.gz`, `.tsv.gz` and `.bed.gz` are all valid. The compression suffix is stripped first, then the primary extension decides the parser.

**Why does the pipeline reject `.xlsx.gz`?**

Excel files are not line-oriented, so they cannot be transparently decompressed. Convert to CSV or TSV first.

**Why does PCA sometimes lower λGC below 1.0?**

If the data has no population structure, PCA over-corrects and removes real signal. Disable PCA (`pca.enabled: false`) when structure is absent.

**Why is Firth slower than standard logistic regression?**

Firth requires an iterative solution to the penalised score equation, while standard logistic regression uses IRLS. The cost is 5–10× in exchange for unbiased estimates under case-control imbalance and perfect separation.

**Can I use BioPipe with BGEN or PLINK 2.x input?**

Not yet. See [roadmap.md](roadmap.md) for planned readers. In the meantime, convert to VCF or PLINK 1.x.

**What is the minimum data size for a meaningful run?**

At least 20 samples for continuous traits; at least 30 cases and 30 controls for binary traits. Smaller datasets run but produce unreliable statistics.

---

## 8. Next steps

- Input contract details: [input_spec.md](input_spec.md)
- Architecture and internals: [architecture.md](architecture.md)
- Adding new readers, steps or pipelines: [developer.md](developer.md)
- Planned features: [roadmap.md](roadmap.md)