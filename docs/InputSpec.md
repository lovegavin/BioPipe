# Input Specification

This document defines every input file BioPipe accepts, the exact column names it requires, and the compression suffixes it tolerates.

Readers are strict. If a file's columns do not match the contract below, the reader raises an error and stops. Column names are not auto-detected. This is intentional: predictable failure is cheaper than silent misinterpretation.

## 1. Overview

| Role | Extension | Compression | Produces |
|---|---|---|---|
| genotype | .vcf | .gz | GenotypeMatrix, VariantTable, SampleTable |
| genotype | .bed (+ .bim, .fam) | none | GenotypeMatrix, VariantTable, SampleTable |
| phenotype | .csv, .tsv, .txt, .xlsx, .xls, .parquet | .gz, .bz2, .xz (text only) | Table |
| covariates | .csv, .tsv, .txt, .xlsx, .xls, .parquet | .gz, .bz2, .xz (text only) | Table |

File names follow a convention inside `input/`:

```text
input/
  genotype.vcf.gz     # or genotype.vcf, or genotype.bed (+ .bim, .fam)
  phenotype.csv       # or phenotype.tsv, .txt, .xlsx, .xls, .parquet
  covariates.csv      # optional, same extensions as phenotype
```

If your files use different names, edit `manifest.yaml` after running `init_task.py`.

## 2. Compression rules

Compression suffixes (`.gz`, `.bz2`, `.xz`, `.zst`) are stripped before the primary extension is inspected.

`.vcf.gz` is a VCF. `.csv.gz` is a CSV. `.gz` alone is not a format.

Excel (`.xlsx`, `.xls`) and Parquet (`.parquet`) do not support compression suffixes. `.xlsx.gz` is rejected.

Compression is transparent to the reader. Column names and formats are unchanged.

| File | Detected as | Accepted |
|---|---|---|
| a.vcf.gz | VCF | yes |
| a.csv.gz | CSV | yes |
| a.tsv.bz2 | TSV | yes |
| a.xlsx.gz | — | no |
| a.gz | — | no (no primary extension) |

## 3. Genotype — VCF

### 3.1 Accepted extensions

`.vcf`, `.vcf.gz`

### 3.2 Requirements

- Follows the VCF 4.x specification.
- Must contain a `GT` field in the `FORMAT` column.
- Sample columns follow the standard VCF sample naming.

### 3.3 Column contract

Columns are defined by the VCF specification and cannot be renamed. BioPipe reads only:

```text
#CHROM  POS  ID  REF  ALT  ...  FORMAT  sample1  sample2  ...
```

### 3.4 Dosage encoding

- Dosage = count of ALT alleles per genotype call.
- Missing calls use `-1.0`.
- Ploidy is inferred from the first non-missing `GT` value.

### 3.5 Missing calls

| Ploidy | Missing notation |
|---|---|
| 2 | `./.` |
| 4 | `./././.` |

### 3.6 Genome build

If the VCF header contains a `##reference` line mentioning GRCh38, hg38, GRCh37, hg19, or b37, the corresponding build label is recorded. Otherwise `"unknown"` is used.

## 4. Genotype — PLINK

### 4.1 Accepted extensions

`.bed` with matching `.bim` and `.fam` files in the same directory, sharing the same stem.

```text
genotype.bed
genotype.bim
genotype.fam
```

### 4.2 Requirements

- PLINK 1.x binary format.
- Diploid only. Polyploid data must be supplied as VCF.

### 4.3 Column contract

Column names are defined by the PLINK specification and cannot be renamed.

```text
.bim:  CHROM  ID  CM  POS  A1  A2
.fam:  FID    IID  PID MID SEX PHENO
```

### 4.4 Allele encoding

| PLINK column | Meaning | BioPipe mapping |
|---|---|---|
| A1 | Effect allele | ALT |
| A2 | Other allele | REF |

This follows the `PLINK --recode vcf` convention. Dosage counts A1 copies.

### 4.5 Missing calls

PLINK missing calls are encoded as `-1.0`.

## 5. Phenotype — CSV / TSV / Excel / Parquet

### 5.1 Accepted extensions

`.csv`, `.tsv`, `.txt` (treated as TSV), `.xlsx`, `.xls`, `.parquet`

### 5.2 Required columns

The file must contain exactly two columns, in this order:

| Position | Column name | Meaning |
|---|---|---|
| 1 | sample_id | Sample identifier |
| 2 | trait_value | Phenotype value |

No other columns are allowed.

### 5.3 Example

```csv
sample_id,trait_value
S001,1.23
S002,0.87
S003,1.05
```

### 5.4 Phenotype type

Detected automatically from the number of unique values in `trait_value`:

| Unique values | Type | Association model |
|---|---|---|
| 2 | Binary | Firth (default) or Logit |
| > 2 | Continuous | OLS |

### 5.5 Error example

If the file uses `id` and `value` instead of `sample_id` and `trait_value`:

```csv
id,value
S001,1.23
```

The reader raises:

```text
Schema mismatch in 'input/phenotype.csv'
  Expected: sample_id, trait_value
  Actual:   id, value
  Hint:     Rename the first columns to match the contract.
            See docs/input_spec.md for details.
```

## 6. Covariates — CSV / TSV / Excel / Parquet

### 6.1 Accepted extensions

Same as phenotype.

### 6.2 Required columns

| Position | Column name | Meaning |
|---|---|---|
| 1 | sample_id | Sample identifier |
| 2+ | any | Covariate columns |

The first column must be `sample_id`. All remaining columns are treated as covariates; names are free.

### 6.3 Example

```csv
sample_id,age,sex,batch
S001,45,1,A
S002,52,0,B
S003,38,1,A
```

### 6.4 Missing values

Covariates must not contain missing values. The association step raises an error if any NaN is found.

### 6.5 Absence

If the manifest declares `covariates: null`, no covariate file is read. If PCA is enabled and `pca.as_covariates` is true, principal components are used as the sole covariates.

## 7. Sample ID rules

- Sample IDs are compared as strings.
- Leading and trailing whitespace is preserved as-is. Ensure genotype, phenotype and covariate files use the same formatting.
- Duplicate sample IDs are rejected.
- Sample alignment is performed by intersection, in the order defined by the phenotype file.

## 8. Common mistakes

| Symptom | Cause | Fix |
|---|---|---|
| `Unrecognized genotype extension: '.vcfq'` | Typo in file extension | Rename to `.vcf` or `.vcf.gz` |
| `Schema mismatch ... Expected: sample_id, trait_value` | Wrong column names | Rename columns exactly as shown above |
| `No common samples` | Sample IDs differ between files | Ensure IDs match across all inputs |
| `Excel does not support compression` | `.xlsx.gz` | Remove the `.gz` suffix |
| `PLINK component missing` | `.bim` or `.fam` not next to `.bed` | Place all three files with the same stem |
| `Unable to infer ploidy from VCF` | No valid GT calls in the file | Check the VCF for GT data |

## 9. What is not supported

- BGEN, PLINK 2.x `.pgen`, Oxford `.gen`
- CRAM, BAM as genotype input
- VCF without a `GT` field
- Polyploid PLINK data
- Column names other than those listed above
- Multi-allelic dosage re-encoding (first ALT allele is used)

Future readers for BGEN and PLINK 2.x are planned. See `roadmap.md`.