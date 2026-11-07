# Restriction digest of phage lambda and pBR322

Restriction digestion with EcoRI, BamHI and HindIII on two classic molecules:
bacteriophage lambda (linear, 48,502 bp) and pBR322 (circular, 4,361 bp).
The route exercises both topology branches of `restriction_digest` and the
fragment length summary.

## Inputs

| Source | File | Size | SHA256 | Notes |
| --- | --- | --- | --- | --- |
| lambda | `input/lambda.fasta` | 49,254 B | `78a78913d3585570fa28b7cec05e4fcf067c1aaa3740d37a377f2babda70618c` | NC_001416.1, 48,502 bp, linear |
| plasmid | `input/pbr322.fasta` | 4,476 B | `2d6aed656794577332720ffaac5352c56ba5cf34e3a173869fbc1aa705b33aeb` | J01749.1, 4,361 bp, circular |

## Steps (8)

1. `restriction_digest` — lambda, linear, EcoRI/BamHI/HindIII
2. `export_results` — `lambda_fragments.csv`
3. `restriction_fragment_stats` — lambda fragments
4. `export_results` — `lambda_stats.csv`
5. `restriction_digest` — pBR322, circular, EcoRI/BamHI/HindIII
6. `export_results` — `plasmid_fragments.csv`
7. `restriction_fragment_stats` — pBR322 fragments
8. `export_results` — `plasmid_stats.csv`

## Results (WSL, 0.0112 s total)

Lambda: 16 cuts, 17 fragments, 48,502 bp; min 493, mean 2,853.06, median 2,027,
max 15,721; 12 fragments >= 1,000 bp, 2 >= 5,000 bp.

pBR322: 3 cuts (HindIII 29, BamHI 375, EcoRI across the origin at 4,359),
3 fragments of 31, 346 and 3,984 bp, total 4,361 bp.

Exports: `lambda_fragments.csv` 1,157 B, `lambda_stats.csv` 206 B,
`plasmid_fragments.csv` 218 B, `plasmid_stats.csv` 199 B.

## Oracle

| Check | Reference | Result |
| --- | --- | --- |
| Cut coordinates | Biopython 1.85 `Restriction.search` (REBASE data) | identical for both molecules |
| Fragment spans and lengths | Biopython recomputation from the same cuts | identical (17 and 3 rows) |
| Lambda EcoRI fragment sizes | classic lambda EcoRI digest {21226, 7421, 5804, 5643, 4878, 3530} | exact |
| Total length | 48,502 / 4,361 bp | exact |

## Limitations

- The enzyme table is a curated set of 29 common enzymes with a single cut
  offset each; isoschizomers, methylation sensitivity and star activity are
  not modelled.
- NC_001416.1 carries six HindIII sites, so the digest has seven fragments:
  the 6,682 bp band merges the classic NEB ladder's 6,557 + 125 bp pair. This
  is a sequence/strain difference, not a digest defect, and the NEB ladder is
  not used as an oracle.
- A circular recognition site spanning the origin is searched by appending the
  first `max(site length) - 1` bases; fragment coordinates may thus exceed the
  sequence length (the caller wraps them).
