# ATAC-seq peak calling on chr22

Calls open-chromatin peaks from paired-end ATAC-seq fragments with a lightweight
local-lambda caller, then merges adjacent peaks. The same fragment BAM is used to
compare against MACS3 and ENCODE IDR peaks.

## Data

| input | source | size | sha256 |
| --- | --- | --- | --- |
| `input/chr22.bam` | ENCODE GM12878 ATAC-seq `ENCFF415FEC.bam`, chr22 subset | 54,427,077 B | `f193f6c3cadd66bfdb4e20a90359374ddd3879a38ae7f46c6915e97329c1ff0d` |
| `input/chr22.bam.bai` | `samtools index` | 30,616 B | - |

The BAM uses `chr22` naming (GRCh38). chr22 carries 1,055,472 mapped fragments
of the 46,956,970 fragments in the full file; all fragments are properly paired.

## Route

Four steps:

1. `atac_peak_call` on the BAM (q-value 0.05, candidate sigma 3.0, 260 bp
   extension, 50 bp merge gap, 100 bp minimum length).
2. `export_results` to `peaks.csv`.
3. `peak_merge` with `max_gap=50`.
4. `export_results` to `merged.csv`.

## Results

| artifact | value |
| --- | --- |
| peaks | 1,854 peaks / 1,287,331 bp / mean width 694 bp |
| merged peaks | 1,840 peaks |
| fragments used | 1,055,472 |

`atac_peak_call` ran in 4.4 s on chr22.

## Oracles

Two independent references were used.

### MACS3 3.0.2

`macs3 callpeak -t chr22.bam -f BAMPE -g hs -q 0.05 --keep-dup all` produced
2,057 peaks / 1,554,495 bp (mean width 756 bp).

| metric | value |
| --- | --- |
| bp Jaccard | 0.4418 |
| MACS bp recall | 0.5602 |
| our bp precision | 0.6645 |
| MACS summit inside our peaks | 1,361 / 2,057 = 66.16% |
| our summit inside MACS peaks | 1,472 / 1,854 = 79.40% |

### ENCODE IDR peaks (chr22 subset)

The ENCODE IDR peak set for this experiment contains 3,326 chr22 peaks
(1,168,598 bp).

| metric | value |
| --- | --- |
| bp Jaccard | 0.5345 |
| IDR bp recall | 0.7321 |

## Limits

- The caller uses a uniform local lambda from 1 kb / 10 kb windows and a global
  genome-wide lambda; it does not implement MACS3's dynamic Poisson model,
  control-sample lambda, or fragment shift model.
- Candidate regions are selected with `lambda + sigma * sqrt(lambda)`; sigma is a
  heuristic, so q-values are approximate and should not be compared directly to
  MACS3 q-values.
- Peaks are extended symmetrically by `extension_bp`; strand-aware extension is
  not modelled.
- The route processes chr22 only; the full BAM is 2.5 GB and not bundled.
- Depth is low (1.05 M chr22 fragments, about 2x), so recall against IDR is
  limited by data rather than only by the algorithm.
