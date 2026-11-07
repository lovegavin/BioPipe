# Codon usage bias of Escherichia coli K-12

## Data

| Input | Source | Size | SHA256 |
|---|---|---|---|
| `ecoli_cds.fasta` | NCBI `GCF_000005845.2_ASM584v2_cds_from_genomic.fna.gz`, CDS extracted, terminal stops removed | 4,043,037 B | `582ca052cc8bb43dc0bc5d88da6d8d7ff7b400308a5830e4cad1f7c7bca9c79f` |
| `ribosomal_reference.fasta` | same assembly, `rps*`/`rpl*`/`rpm*` products (54 CDS) | 21,762 B | `b60758e791591d2630d59e982ec47d82819ddb22121dc72afe9700cecdee7640` |

## Steps

1. `codon_usage_bias` — ENC (Wright 1990), GC3s and codon count per CDS.
2. `export_results` — `codon_usage_bias.csv`.
3. `codon_adaptation` — CAI (Sharp & Li 1987) against the ribosomal reference.
4. `export_results` — `codon_adaptation.csv`.
5. `rscu_table` — aggregated RSCU over all CDS.
6. `export_results` — `rscu_table.csv`.

## Results

| Metric | Value |
|---|---|
| CDS analysed | 4,313 |
| ENC defined | 4,217 (96 CDS lack a polymorphic family in at least one degeneracy class) |
| ENC min / mean / max | 23.9462 / 46.9996 / 61.0 |
| CAI min / mean / max | 0.0704 / 0.3905 / 0.8751 |
| Highest RSCU | CTG 2.9918, CGC 2.4075, CGT 2.3010 |

## External checks

| Oracle | Comparison | Result |
|---|---|---|
| CodonW 1.4.4 (`-enc -gc3s`) | ENC over 4,217 genes | max abs 0.0050 (CodonW prints two decimals) |
| CodonW 1.4.4 (`-gc3s`) | GC3s over 4,217 genes | max abs 5.0e-4 (CodonW prints three decimals) |
| R 4.3.3 independent implementation | CAI over 4,313 CDS | max abs 5.6e-16 |
| R 4.3.3 independent implementation | RSCU over 61 codons | max abs 4.7e-15 |

## Conventions and limitations

- ENC follows the CodonW/Wright definition: families that are monomorphic or observed once do not enter the average, and ENC is undefined (NaN) when a degeneracy class has no polymorphic amino acid; the isoleucine exception averages the 2- and 4-fold classes.
- CAI uses Sharp & Li weights `count / max`; codons absent from the reference receive the recommended floor `0.5 / max` so that a single missing codon does not force CAI to zero.
- The reference set is 54 ribosomal proteins, not a curated highly-expressed gene set, so CAI is relative to that reference only.
- RSCU aggregates every CDS equally; it is not weighted by expression.
