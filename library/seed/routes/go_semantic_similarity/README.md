# GO semantic similarity

## Data

| Input | Source | Size | SHA256 |
| --- | --- | --- | --- |
| `go-basic.obo` | Gene Ontology release 2026-07-26 | 32,227,785 B | `b08d45b268b8c24ccb2513dbbbc7d4df9f6521c099b413f79eb31e06e0fa3bcc` |
| `ecocyc.gaf.gz` | EcoCyc GAF 2.2 (E. coli K-12, aspect P) | 1,097,004 B | `edd882f3c9c538119b93c040522f6bc3b84f199566dc1236387fc953350c8f01` |

The OBO file contains 48,340 terms. The GAF file contributes 5,550 annotated genes in the
biological-process aspect. The route samples the 300 most frequently annotated terms and
builds 300 random term pairs and 300 random gene pairs (at least three annotations each,
seed 7).

## Route

`terms.csv` → `go_ic_profile` → export; `pairs.csv` → `go_term_similarity` → export;
`gene_pairs.csv` → `go_gene_similarity` → export (six steps).

## Reference values

- `go_ic_profile.csv`: 300 rows, e.g. GO:0006355 information content 3.1551837 bits with
  623 annotated genes, depth 9, 2 parents.
- `go_term_similarity.csv`: 300 pairs with Resnik, Lin, Jaccard and the two term IC values.
- `go_gene_similarity.csv`: 300 gene pairs; mean best-match average 1.1321 and mean
  maximum similarity 1.9155.

Propagation follows the **is_a** relation only, matching the common GO semantic-similarity
convention used by goatools and GOSemSim. Information content is `-log2(count / 5550)`.

## Oracles

| Oracle | Version | Metric | Result |
| --- | --- | --- | --- |
| goatools | 1.6.9 | IC, annotations, depth, parents, Resnik, Lin, Jaccard, BMA | max abs ≤ 8.88e-16 |
| base R | 4.3.3 | same metrics, independent parser | IC/Resnik/Lin/Jaccard exact; BMA 4.44e-16 |

## Limitations

- Only the biological-process aspect is exercised; the operators accept `aspect` values
  `P`, `F`, `C` and `all`.
- The OBO parser keeps `is_a` edges only; `part_of` and other relations are ignored.
- Semantic similarity is computed on the annotation sets as provided; no true-path
  propagation is applied beyond ancestor expansion for counting.
