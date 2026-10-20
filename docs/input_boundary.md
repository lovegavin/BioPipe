# Input boundary

BioPipe is an analysis layer, not a sequencing or imaging pipeline
front end. Every analysis route starts from data that a prior,
specialised tool has already produced. This document fixes that
boundary so that route design does not reopen the question on
every new pipeline.

## What "start of analysis" means here

The input to a BioPipe route is **analysis-ready data**: a table,
a matrix, a variant call set, an annotation, a coordinate list,
or a sequence. BioPipe does not align reads, call variants,
quantify transcripts, segment images, or pick peaks. Those steps
happen before BioPipe, in tools built for them (BWA, STAR,
Salmon, Cell Ranger, GATK, MACS2, MetaPhlAn, MSFragger, and so
on), and their outputs are what BioPipe consumes.

This boundary is hard. It does not move because a user wants
end-to-end. When an end-to-end run is needed, the upstream
toolchain is invoked outside BioPipe (for example a Nextflow or
nfel-core pipeline), and its analysis-ready outputs are the
`sources` of a BioPipe task.

## Supported starting files

Every file below is a supported `sources` entry today. The
"Limits" column states what the Reader does **not** silently
accept.

### Tables (any domain)

| Reader | Extensions | Start-of-analysis definition | Limits |
| --- | --- | --- | --- |
| CsvReader | `.csv` | Two-dimensional table with a header row | None |
| TsvReader | `.tsv` | Tab-separated two-dimensional table | None |
| TxtReader | `.txt` | Two-dimensional table, delimiter configurable | None |
| ParquetReader | `.parquet` | Columnar two-dimensional table | Not used by any route yet |

### Sequences

| Reader | Extensions | Start-of-analysis definition | Limits |
| --- | --- | --- | --- |
| FastaReader | `.fasta` `.fa` `.fna` `.faa` | Nucleotide or protein sequences | No per-base quality scores |

### Genome annotation

| Reader | Extensions | Start-of-analysis definition | Limits |
| --- | --- | --- | --- |
| Gff3Reader | `.gff` `.gff3` | 9-column GFF3 annotation | None |
| GtfReader | `.gtf` | 9-column GTF annotation | None |

### Genotypes

| Reader | Extensions | Start-of-analysis definition | Limits |
| --- | --- | --- | --- |
| VcfReader | `.vcf` `.vcf.gz` | Variant call set, hard calls | Output representation is `hard_call`; no dosage or genotype-probability path |
| Plink1Reader | `.bed` + `.bim` + `.fam` | Genotype matrix, hard calls | Requires all three files |
| Plink2Reader | `.pgen` + `.pvar` + `.psam` | Genotype matrix, hard calls | Requires all three files |
| BgenReader | `.bgen` | Expected ALT dosage from genotype probabilities | Biallelic diploid only. Haploid, haplotype and complex BGENs raise `ReaderError`. Non-biallelic files must be converted to VCF first. |

### Intervals

| Reader | Extensions | Start-of-analysis definition | Limits |
| --- | --- | --- | --- |
| BedReader | `.bed` | UCSC BED, 3 to 12 columns | 0-based half-open coordinates |

### Single cell

| Reader | Extensions | Start-of-analysis definition | Limits |
| --- | --- | --- | --- |
| H5adReader | `.h5ad` | AnnData expression matrix plus metadata | None |
| MtxReader | 10x MEX directory | `matrix.mtx`, `barcodes.tsv`, `features.tsv` | Standard 10x layout only |

### Functional annotation

| Reader | Extensions | Start-of-analysis definition | Limits |
| --- | --- | --- | --- |
| GafReader | `.gaf` | GO association file, 17 columns | None |

## Explicitly out of scope

The following are **not** supported starting files. Adding any of
them is a product decision, not a Reader contribution.

### Sequencing front end

- FASTQ (`.fastq`, `.fq`, `.fastq.gz`)
- Illumina BCL directories
- Oxford Nanopore FAST5 / POD5

### Alignment products

- SAM, BAM, CRAM

### Mass spectrometry

- Thermo `.raw`, Bruker `.d`, Sciex `.wiff`
- mzML, mzXML

### Imaging

- Zeiss `.czi`, Leica `.lif`, Nikon `.nd2`, Olympus `.oir`
- OME-TIFF
- Cryo-EM MRC / MRC stacks

### Array front end

- Illumina `.idat`
- GenomeStudio probe-intensity exports

### Other measurement formats

- Flow cytometry FCS
- Electrophysiology ABF
- NMR FID
- Crystallography `.cbf`, `.img`, `.hkl`

### Any intermediate format that requires a domain-specific
### preprocessing step to be meaningful

This is the actual rule behind the list above. If reading the
file does not produce a matrix, a table, an annotation, or a
coordinate list that an operator can compute on directly, the
file is out of scope.

## What this boundary implies for routes

- A route starts from analysis-ready data, not physical raw data.
- A user who has FASTQ must first run the standard upstream
  toolchain (for example nf-core/rnaseq, nf-core/scrnaseq,
  nf-core/sarek). The resulting count matrix, AnnData, or VCF
  is the route's `sources`.
- BioPipe is not a replacement for Nextflow, nf-core, Galaxy, or
  vendor software. It is the layer after those tools.

## Admission criteria for a new Reader

A new Reader is accepted only when all of the following hold:

1. **Real public data exists.** The file can be downloaded from
   a reproducible URL. Synthetic fixtures are not enough.
2. **An external numerical reference exists.** The Reader's
   output can be validated against a published value or an
   independent implementation.
3. **At least one route uses it.** A Reader with no route is
   dead code and is not merged.
4. **It is not an intermediate format of a preprocessing
   pipeline.** Unless that pipeline itself is the route's
   declared start, the Reader is out of scope.

If any of the four fails, the contribution is rejected. This is
the same rule that led to the `BgenReader` change in v5 patch 3,
where the accepted input was narrowed to biallelic diploid only
because the reader previously produced a wrong `Form` for
haploid, haplotype, and complex BGEN files.
