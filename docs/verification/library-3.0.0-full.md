# Operon Operator Library v3.0.1 — Full Verification Report

Verification date: 2026-11-05. Baseline tree: the `release/3.0.0` worktree, branch
`release/3.0.0`, commit `df081f71`. Application/backend **3.0.0**; Operator
Library **3.0.0** verified in place and released as patch **3.0.1** (the
`library-v3.0.0` tag is immutable, so all fixes in this report ship in
`library-v3.0.1`). `minimum_application = build_application = 2.4.1`.

This report answers one question for every operator: **can its output be
exported, and by which path?** It also records the runtime evidence, the
external oracles, the product defects fixed, and everything intentionally not
covered.

## 1. Environment

| Item | Value |
| --- | --- |
| OS | WSL Ubuntu-24.04 (Linux 6.6 x86_64) |
| GPU | NVIDIA RTX 3090, 24 GB |
| Python | 3.12.14 (`operon` conda environment) |
| Application | Operon 3.0.0 (editable install in the same env) |
| Library | 3.0.0 (this tree), released as 3.0.1 |
| Minimum application | 2.4.1 |
| Registry | 717 operators / 101 Readers / 7 packages / 24 routes, `errors []` |

Key external tools used for routes and oracles:

| Tool | Version | Domain |
| --- | --- | --- |
| QUAST | 5.3.0 (conda `assembly`) | assembly |
| Flye | 2.9.6 | assembly |
| mkdssp | 4.2.2 | structure |
| Biopython | 1.88 | structure / sequence |
| tmtools | 0.3.0 | structure |
| ViennaRNA (`RNAfold`/`RNAduplex`/`RNAcofold`/`RNAsubopt`) | 2.5.1 | RNA |
| antiSMASH | 8.0.4 + module DBs | annotation |
| AMRFinderPlus | 4.2.7 + 2026-10-29.1 DB | annotation |
| Infernal `cmscan` / Rfam | 1.1.5 / Rfam.cm | annotation |
| tRNAscan-SE | 2.0.12 | annotation |
| HMMER `hmmsearch` | 3.4 | annotation |
| Prodigal | 2.6.3 | annotation |
| RDKit | 2025.03 | small molecule |
| PoseBusters | 0.6.5 | docking |
| AutoDock Vina (Python) | 1.2.7 | docking |
| scanpy | 1.12.5 | single cell |
| scikit-bio | 0.7.4 | microbiome |
| statsmodels / SciPy / scikit-learn | 0.15 / 1.16 / 1.6.1 | statistics |

R, limma, DESeq2, EMBOSS, DockQ and hictkpy were not available in the base
environment. Where they were required for a route they were supplied from a
side overlay (`/tmp/hicenv` for Hi-C) or the check is marked SKIP; no oracle was
simulated with the implementation under test.

## 2. Method

1. **Static inventory** of all 717 operators (AST + registry metadata):
   `id`, category, arity, output kind, output dimensionality, `result_files`
   registration, native formats, `info.sequences` usage, file-writer hints.
   Saved as `/tmp/op_inventory.json`.
2. **Runtime export matrix**: every format against 1D/2D/3D/empty/sequence
   Forms, `FileArtifact` inputs, and all 16 native-file producers. Each cell was
   executed through the real runner; bytes were compared with SHA-256, output
   paths checked against `out_dir`, idempotency and error paths checked.
3. **Native-file audit** of every step module that writes `.pdb`, `.cif`,
   `.pqr`, `.pdbqt`, `.fasta` or `.fa`.
4. **Classic routes**: all 24 builtin routes plus the real-data examples were
   checked and executed with `scripts/run.py` (real runner, real memory budget).
5. **External oracles**: independent implementations for assembly, structure,
   sequence/RNA, statistics, single cell and GWAS. Same-implementation checks
   (e.g. wrapping antiSMASH and comparing to antiSMASH) are not counted as
   oracles and are labelled as such.
6. **Full suite** run once at the end: `pytest -q` (log
   `/tmp/full_pytest_301.log`), plus registry check, docs check, packaging
   group, and `git diff --check`.

Evidence is under `/tmp/verify/`: `export_form`, `export_file`, `genome`,
`omics_sc`, `omics_tx`, `rna_seq`, `design`, `hic`, `structure`, `routes_csv`,
`routes_special`, `route_extra`, `native_audit`, `gtf_fix`.

## 3. Operator inventory (717)

| Property | Count |
| --- | --- |
| Operators | 717 |
| Form-only outputs | 714 |
| `FileArtifact` outputs | 3 (`export_results`, `align_reads`, `build_contacts`) |
| Native files registered (`result_files`) | 16 producers (+ `export_results` itself) |
| Operators attaching `info.sequences` | 33 |
| Modules with file-writer code | 46 |
| Output ndim 2 / 0 / 3 / 1 | 654 / 59 / 3 / 1 |

Category distribution as declared in the registry (mixed legacy spellings are
preserved verbatim):

| Category | Count |
| --- | --- |
| Statistics | 261 |
| Machine Learning | 224 |
| Omics | 57 |
| Structure | 53 |
| Sequence | 21 |
| Data + data | 22 |
| 数据整理 | 16 |
| analysis + Analysis | 14 |
| 可视化 + Visualization + visualization | 15 |
| 统计分析 | 12 |
| Genome | 7 |
| Quality Control + 质量控制 | 8 |
| Docking | 3 |
| data preparation | 2 |
| Ligand / Antibody | 2 |

The practical conclusion: **714 of 717 operators are Form producers and need no
per-operator export work** — `csv`/`tsv` (2D), `npy` (any numeric shape) and
domain writers cover them. Only 16 producers own a native file that can be lost
if not registered.

## 4. Export capability matrix

`export_results` supports `auto`, `native`, `csv`, `tsv`, `npy`, `fasta`, `pdb`,
`cif` plus the domain formats `genbank`, `bed`, `bedgraph`, `graphml`, `newick`,
`hic`, `cool`. The matrix below is the observed behaviour, not the intended
one.

| Format | Form | FileArtifact / native | Verdict |
| --- | --- | --- | --- |
| `auto` | 2D→CSV, other→NPY | passes original files through | PASS |
| `native` | n/a (error) | all registered files, byte-identical | PASS |
| `csv` | 2D only | original `.csv` reused | PASS; 1D/3D UNSUPPORTED by design |
| `tsv` | 2D only | original `.tsv` reused | PASS; 1D/3D UNSUPPORTED by design |
| `npy` | all numeric dtypes/shapes | original `.npy` reused | PASS; labels/info intentionally not stored |
| `fasta` | needs `info.sequences` | original FASTA reused | PASS when sequences present; otherwise explicit error |
| `pdb` | rejected | original PDB copied | PASS; tensor reconstruction is deliberately unsupported |
| `cif` | rejected | original mmCIF copied | PASS; same native-only rule |
| `genbank` | n/a | original GenBank copied | PASS (byte-identical, features intact) |
| `bed` | n/a | BED FileArtifact | PASS (`chr1 0 50`, `chr2 100 250`, `chrX 1000 1500`) |
| `bedgraph` | n/a | bedGraph FileArtifact | PASS (1.5 / 2.25 / -4.0) |
| `graphml` | n/a | GraphML FileArtifact | PASS (3 nodes, 2 undirected + 4 directed edges) |
| `newick` | n/a | Newick FileArtifact | PASS (leaves A, B, C) |
| `hic` | n/a | Hi-C FileArtifact | PASS (copy + reopen) |
| `cool` | `Form` conversion SKIP (no `hictkpy`) | Cooler FileArtifact | PASS for FileArtifact; Form→cool SKIP |

Runtime checks that apply to every PASS cell:

- **Byte identity** — 45 exports across 15 producers had matching SHA-256; the
  16th (`esm3_fold`) was SKIP because the `esm3` package is absent.
- **Path containment** — all exported paths resolve inside the task `out_dir`;
  `..`, absolute paths, drive letters and separators in `filename` are rejected.
- **Multi-file** — ProteinMPNN (2), RFdiffusion (2), flexible receptor (2) and
  Vina batch (2) produce numbered outputs without collisions.
- **Idempotency** — repeated export of the same artifact yields identical
  bytes; re-install/re-run does not change hashes.
- **Error paths** — missing native file, cross-task Form without FileArtifact,
  non-2D CSV/TSV, object-dtype NPY and FASTA/axis mismatch all raise
  `StepError`, never a silent partial file.
- **FASTA alignment** — headers come from first-axis labels, multi-chain names
  become `name|chain=N`, 80-column wrapping, and sequence count must equal the
  first-axis length.
- **PDB/CIF** — never rebuilt from the atom tensor. A structure Form without a
  native file is an explicit UNSUPPORTED, not a lossy guess.

One cosmetic observation, not a contract violation: a failed `pdb`/`cif` export
can leave an empty `exports/<uuid>/` directory behind. No file is produced and
no data is corrupted; it is recorded here rather than patched, because changing
`export_results` is out of scope for 3.0.1.

## 5. Native-file registration audit

The 16 producers that register `result_files`, all exercised through
`export_results(format=native)` and, where applicable, `format=pdb`/`fasta`.
Export wiring was driven by deterministic fake tool outputs; the real-tool
native runs separately recorded are ProteinMPNN on 1MEL chain A (132 aa,
score 0.744, recovery 56.1%), ESMFold 42 aa (pLDDT 82.90), Boltz-2 20 aa
(confidence 0.803, pTM 0.387), Flye lambda (47,913 bp contig) and Vina
aspirin docking; each exported file was SHA-256 identical to the tool output:

| Producer | Native format |
| --- | --- |
| `boltz_predict` | PDB |
| `boltz_complex_confidence` | PDB |
| `colabfold_predict` | PDB |
| `openfold_predict` | PDB |
| `esmfold_predict` | PDB |
| `esm3_fold` | PDB |
| `flye_assemble` | FASTA |
| `ligand_pdbqt_prepare` | PDBQT |
| `ligand_pdbqt_flexible` | PDBQT |
| `ligandmpnn_side_chain_packing` | PDB |
| `proteinmpnn_design` | FASTA + CSV |
| `rfdiffusion_design` | PDB |
| `structure_pdbqt_flexible_receptor` | PDBQT |
| `vina_dock` | PDBQT |
| `vina_dock_batch` | PDBQT |
| `vina_dock_python` | PDBQT |

The six operators previously suspected of missing registration were audited and
are **not** product defects: `structure_openmm_energy` (energy table only),
`structure_openmm_md_stability` (input in a temporary dir), `structure_protonation_pka`
(PQR is read for charges), `interface_alanine_scan` (mutant PDB is only an
OpenMM input), `structure_pocket_detect` and `structure_openmm_md_rmsf`
(intermediate files). They do not produce a user-facing native artifact, so
inventing a `result_files` entry would have been cosmetic.

Known metadata hygiene issues, documented but not fixed in 3.0.1 because they
do not lose user data: `colabfold_predict` (fixed in 3.0.1), `boltz_predict`
confidence/affinity JSON paths, `structure_pocket_detect` info path,
`structure_openmm_md_rmsf` trajectory/prepared PDB paths,
`structure_ligand_pose_qc` input paths, and `vina_dock_batch` log paths point at
temporary directories or outside `out_dir`. The files themselves are not user
outputs; the fix is to stop reporting them, not to register them.
## 6. Classic routes (24/24)

All builtin routes were checked first (`run.py <dir> --check`) and then executed
with the real worker. "Wall" is the `run.py` wall time from the evidence JSON
or log; it includes interpreter start-up. The five real-data examples
(`gwas`, `rnaseq_de`, `proteomics_de`, `survival`, `microbiome`) are part of the
24.

| Route | Steps | Status | Key result | Wall |
| --- | --- | --- | --- | --- |
| `bgen_qc` | 8 | PASS | 199 variants × 500 samples; 99,498 valid genotypes, 2 missing; PC1 EVR 0.020074 | — |
| `go_enrichment` | — | PASS | 30 genes × 7 terms; all 7 P-values equal SciPy hypergeom; 3 q<0.05 | — |
| `gtf_annotation` | 8 | PASS | 23 GTF records; 5 genes; 2 gaps, largest 2,999 bp | 0.433 s |
| `gwas` | 16 | PASS | 1,651 records → 99 MAF → 78 tested → 19 FDR; λGC 2.66; lead `22:16053659:C` p=5.76e-10 | 3.63 s |
| `gwas_meta_prs` | 4 | PASS | 99 variants, 24 q<0.05; max I²=84.29; λGC 1.26 | 1.25 s |
| `hic_bam` | 5 | PASS | BAM→pairs→cool→heatmap; 20 bins | 11.92 s |
| `hic_fastq` | 7 | PASS | 20,000 pairs; heatmap 20×20 | 15.24 s |
| `hic_pairs` | 5 | PASS | canonical pairs→cool→heatmap 100×100 | 11.92 s |
| `interval_analysis` | — | PASS | 6→5 intervals / 1,100 bp; 5 overlaps of 400 bp; median 175 | — |
| `microbiome` | 13 | PASS | 34 samples × 770 taxa, 153,807 counts; PERMANOVA F=8.5712, R²=0.6048, P=0.001 | 1.76 s |
| `microbiome_diff` | 8 | PASS | 20 taxa; ANCOM-BC 17 vs ALDEx2 0 at q<0.05 (sensitivity gap documented) | 2.45 s |
| `ml_classification` | 11 | PASS | logistic acc .800/AUC .913; RF .867/.917; GB .600/.773 | 3.45 s |
| `ml_regression` | 11 | PASS | ridge R² .463; RF −.012; GB reported | 2.49 s |
| `multi_omics` | 14 | PASS | CITE-seq 60 genes + 32 antibodies; 3,540 pairs; max corr .987 | 3.47 s |
| `proteomics_de` | 7 | PASS | 4 proteins / 16 peptides; DE table + volcano + MA | 2.87 s |
| `proteomics_limma` | 7 | PASS | 60 proteins, 8 DE; logFC −2.67..3.16 (raw-intensity scale, documented) | 2.62 s |
| `rnaseq_de` | — | PASS | pydeseq2 installed; DE table produced | 4.08 s |
| `rnaseq_de_enrichment` | 7 | PASS | 40 genes, 6 q<0.05; GSEA SET0 NES 1.465, Q 0.0199 | 3.07 s |
| `rnaseq_ssgsea` | 6 | PASS | 16 samples × 4 sets; scores −0.310..0.587 | 2.53 s |
| `sequence_features` | 9 | PASS | 3 sequences (258/276/212 bp); 13 complete ORFs; 4 motif hits; 3 PNGs | 0.80 s |
| `single_cell` | 14 | PASS | 10x PBMC3k 2,700 × 32,738 → 13,714 genes; 15 Louvain clusters; 145.8 s; managed peak 712 MB but admission needs 16 GB (1/4 GB budgets rejected up front) | 145.8 s |
| `single_cell_batch` | 7 | PASS | 120 × 60 ComBat; marker directions correct | 3.87 s |
| `single_cell_loom` | 11 | PASS | 120 × 80 loom; doublets 0 (synthetic data too shallow) | 6.21 s |
| `survival` | — | PASS | KM + Cox table | — |

Additional real-data examples executed during the omics audit: PBMC3k atlas
(12/12, 171 s), leukemia GCT (11/11, 12.29 s), thousand-genomes chr22 GWAS,
refseq CDS features, and the QIIME moving-pictures microbiome (13/13).

## 7. External oracles

Only independent implementations count as oracles. Wrapping the same tool the
operator calls (e.g. antiSMASH-vs-antiSMASH) is explicitly not listed here.

| Domain | Oracle | Metric | Operator | Oracle | Delta | Tolerance |
| --- | --- | --- | --- | --- | --- | --- |
| Assembly | QUAST 5.3.0 | N50 / L50 / total / largest / genome fraction | 30 / 2 / 100 / 40 / 98.779% | 30 / 2 / 100 / 40 / 98.779% | 0 | exact (6/6) |
| Structure | Biopython 1.88 | interface buried area (1MEL A–L) | 1,669.157 Å² | 1,645.721 Å² | +1.42% | ±5% |
| Structure | Biopython 1.88 | total SASA | 21,803.086 Å² | 21,750.841 Å² | +0.24% | ±1% |
| Structure | mkdssp 4.2.2 | backbone H-bonds | 363 | 364 | −0.27% | ±2% |
| Structure | tmtools 0.3.0 | TM-score (self) | 1.0 | 1.0 | 0 | ±1e-6 |
| Sequence | Biopython ProtParam 1.88 | molecular weight (VHH, 132 aa) | 13,877.2334 Da | 13,877.1602 Da | +0.0732 Da (5.3 ppm) | ±50 ppm |
| Sequence | Biopython ProtParam 1.88 | GRAVY / aromaticity | −0.203 / 0.1212 | −0.203 / 0.1212 | 0 | exact |
| RNA | ViennaRNA 2.5.1 | MFE (tRNA-Phe) | −22.40 kcal/mol | −22.40 | 0 | exact |
| RNA | ViennaRNA 2.5.1 | duplex ΔG | −83.50 | −83.50 | 0 | exact |
| RNA | ViennaRNA 2.5.1 | cofold MFE / binding | −62.00 / −31.94 | −62.00 / −31.94 | 0 | exact |
| Statistics | statsmodels 0.15 / SciPy | DE P-values, log2FC, GWAS beta | — | — | max |ΔP| 6.31e-7; Pearson ≥ 0.99999999999984 | ±1e-6 |
| Single cell | scanpy 1.12.5 + sklearn | PCA + KMeans(k=8) ARI | 0.896 | — | — | ≥0.85 |
| Microbiome | scikit-bio 0.7.4 | PERMANOVA F / R² / Shannon | 8.5712 / 0.6048 | — | F Δ1.3e-7, R² Δ8e-9, Shannon Δ4e-8 | ±1e-6 |

The pI implementation remains divergent and is **not** claimed as passing:
`protein_properties` reports 4.6040, `sequence_isoelectric_point` 4.6288, and
ProtParam 4.8714 for the same VHH. The two in-repo pKa tables disagree; this is
recorded as a known inconsistency, not fixed in a patch release because it
changes scientific output for existing workflows.

## 8. Defects fixed in 3.0.1

Every fix has a failing-before / passing-after regression test. Tests live in
`tests/test_extension357.py` (14 cases) and `tests/test_extension358.py`
(GTF roles), with the pinned values in `tests/test_extension11.py` and the DSSP
contract in `tests/test_extension280.py`. Combined run: **26 passed**.

| # | Operator | Defect (before) | Fix | Evidence |
| --- | --- | --- | --- | --- |
| A | `structure_interface_core` | third-party chain burial counted in the A–L interface: 54 interface / 33 core / 21 rim, ΔSASA 2,034.31 Å² (+21.9% vs BSA) | `relative_sasa` takes `complex_mask`; complex SASA only over the two partner chains | after: 46/28/18, ΔSASA 1,669.157 = BSA 1,669.157 |
| B | `structure_dssp_segments` | line filter accepted DSSP statistics rows; `tokens[4]` read BP1 as chain; 192 segments / 524 residues with chains `"12"`, `"3"`, `"0"`… | fixed columns: resnum `[5:10]`, chain `[11]`, aa `[13]`, SS `[16]`; empty code → `-` | after: 187 segments / 518 residues, every state count equals the mkdssp oracle |
| C | `ligand_pdbqt_flexible` | `export()` omitted `result_files`; `export_results(native)` failed with “no matching original native file” | add `"result_files": result_files` | T2.11/T2.11b PASS; sha256 match, 3 exports |
| D | `vina_dock_batch` | two ligands with the same stem wrote `poses.pdbqt` to one path; `poses_1`/`poses_2` pointed at the same file | `run_ligand(tag=...)` uses the unique label as filename stem | two distinct output files, no overwrite |
| E | `assembly_stats` | launched `quast.py` with `sys.executable`, losing the conda env → `ModuleNotFoundError: No module named 'quast_libs'`; on Windows the old fallback never triggered because `os.access(X_OK)` is always true, so a `.py` entry point was executed directly → `OSError: [WinError 193]` | `_launcher()` executes the tool directly when its shebang is usable and always uses `sys.executable` for `.py` on Windows (`os.name == "nt"`) | real QUAST run passes; Windows `test_run_with_fake_quast` passes |
| F | `antismash_bgc` | GenBank input with both `gene` and `CDS` features counted every gene twice (11 genes → 22) | deduplicate by `locus_tag`, falling back to span | n_genes 11, region count unchanged |
| G | `vina_dock_python` | default `seed=0` made repeated runs differ (−5.131 vs −5.125, different pose hashes) | default seed 42 in code and parameter JSON | two runs identical energy and pose sha |
| H | `colabfold_predict` | `info.scores_path` pointed into a `mkdtemp` directory removed in `finally` | copy scores into `output_directory(ctx,"colabfold")`, report the copy as a result file | file exists after run; `result_files` includes it |
| I | `protein_properties` | molecular weight added +18.01524 per residue; VHH 16,255.25 vs 13,877.16 (+17.13%) | `sum(mono) − 18.01524·(n−1)` | 13,877.2334 (5.3 ppm) |
| J | `sequence_rna_fold` | no `-p`; ensemble was always NaN | add `-p` and parse the `struct [ … ]` ensemble line | ensemble `[-22.40, -24.13, -3.01, 16.21, 0.0607, 23.38, 21]` |
| K | `sequence_rna_cofold` | energy regex only matched parentheses; structure regex rejected commas | accept `()`/`[]`; include commas in the structure class | ensemble −62.54; MFE/binding equal CLI |
| L | `sequence_rna_duplex` | default `energy_range=0.0` silently produced no records for a 40-nt hairpin + complement | floor at 0.1 kcal/mol in code and parameter JSON | duplex −83.50 reproduced |
| M | `gff_feature_stats`, `gene_structure`, `annotation_gaps` | hard-coded GFF column names; GTF input failed at step 1 with “field dim 'field' has no 'type' label” | use `_annotation_columns.require_role` (`seqname↔seqid`, `feature↔type`, `attribute↔attributes`) | GTF route 8/8, 0.433 s |

The GTF route is the end-to-end proof for M: a 23-record yeast GTF now runs
`gff_feature_stats → gene_structure → annotation_gaps` and reports 5 genes and
2 gaps (largest 2,999 bp).

## 9. Behavioural findings documented, not patched

These are real numerical or API observations. They were not changed in 3.0.1
because a patch must not silently alter scientific results; they are candidates
for the next minor release.

1. **pI divergence** — two pKa tables in the repo (`protein_properties.py:24`,
   `sequence_isoelectric_point.py:15`) yield 4.6040 vs 4.6288; ProtParam 4.8714.
2. **Proteomics “logFC”** — `proteomics_limma` reports raw intensity differences
   (`limma_de.py:155`, parameter JSON), not log2 ratios. The route is
   numerically correct for its stated scale but the column name is misleading.
3. **Microbiome differential sensitivity** — ANCOM-BC calls 17/20 taxa,
   ALDEx2 0/20 on the same synthetic table; this is a method-sensitivity
   difference, not a crash.
4. **GWAS model** — the route uses no PCA covariates and HWE 1e-4 filtering,
   which removed 21/99 variants including the causal one; λGC 2.66 on the
   example is expected under that model.
5. **`compare_groups` signed data** — for signed matrices log2FC becomes
   `None` for 2,443/10,056 genes.
6. **Quantile normalization** — `normalize.py:83,200` ignores `target_sum` for
   the quantile method.
7. **ML logistic importance** — multiclass coefficients are averaged and cancel
   to ~1e-14 in `top_features`; predictions are unaffected.
8. **Loom z-score input** — raw z-scored loom matrices contain negative values,
   so CPM fails with 233/400 non-positive genes; min-shift is the documented
   workaround and the negative-control behaviour is intentional.
9. **Metadata path leaks** — listed in §5; no user data is lost.
10. **Empty export directory** — failed `pdb`/`cif` export leaves an empty
    `exports/<uuid>/`; cosmetic only.
## 10. Coverage

| Scope | Coverage |
| --- | --- |
| Static export audit | 717 / 717 operators inventoried; output kind, ndim, native registration, `info.sequences`, writer hints |
| Export matrix | 17 formats × Form shapes × FileArtifact/native producers; 71 numbered checks (34 in `export_form`, 37 in `export_file`) |
| Native producers | 16 / 16 export wiring (deterministic fake tool outputs), `esm3_fold` SKIP: package absent; five real-tool runs recorded in §5 |
| Builtin routes | 24 / 24 checked and executed; 221 step entries, 75 distinct operators |
| Real-data examples | 5 / 5 (PBMC3k, QIIME, leukemia, chr22 GWAS, RefSeq CDS) plus PBMC3k 10x matrix, λ phage, 1MEL, nisin BGC |
| External oracles | 7 domains, 14 numeric comparisons |
| Regression tests added | 14 tests (`tests/test_extension357.py` 13, `tests/test_extension358.py` 1) |
| Full suite | `pytest -q`, result in §14 |

Route coverage (75 distinct operators) is intentionally narrower than the
717-operator inventory: a route proves integration, not every operator. The
remaining operators are covered by the static export audit and by the existing
unit suite; no claim is made that every one of the 717 was executed against
real data.

## 11. Not covered, and why

| Item | Status | Reason |
| --- | --- | --- |
| `esm3_fold` native export | SKIP | `esm3` package not installed; no weight download attempted |
| `esm3_sequence_generation` and other ESM-3 operators | SKIP | same missing package |
| `export_results(format="cool")` from a plain Form | SKIP | `hictkpy` absent in the base env; FileArtifact→cool verified in the overlay |
| DockQ external oracle | SKIP | DockQ imports fail under numpy 2.1.3; the operator's self-comparison is 1.0 but is not an independent check |
| R / limma / DESeq2 oracle | NOT AVAILABLE | R not installed; statsmodels/scipy approximations used and labelled as such |
| EMBOSS oracle | SKIP | not installed |
| ESMFold via `esm.pretrained` | ENV BUG | `esm` 3.4.2 namespace shadows fair-esm 2.0.0 (`AttributeError: module 'esm' has no attribute 'pretrained'`); the route-level ESMFold run used the working path and produced pLDDT 82.90 |
| 59 zero-dimensional operators | STATIC ONLY | no meaningful tabular export beyond `npy`; included in the 714 Form-only count |
| GPU numerical reproducibility across model versions | NOT CLAIMED | Boltz/ProteinMPNN numbers are for the pinned weights and versions in §1 |

The `single_cell` route needs `--memory-mb 16384` for the full PBMC3k matrix
(2,700 × 32,738). With 1 GB and 4 GB the runner correctly refuses admission
(`MemoryBudgetError`) instead of thrashing; this is expected behaviour for a
dense matrix of this size, not an operator bug.

## 12. Release 3.0.1

The `library-v3.0.0` tag and its assets are immutable, so this verification
batch ships as **Operon Operator Library v3.0.1**:

- `library/release.json`: `version 3.0.1`, `minimum_application 2.4.1`,
  `build_application 2.4.1`.
- `library/pyproject.toml`: `version = "3.0.1"`.
- Tag: `library-v3.0.1`; release note:
  `docs/releases/library-v3.0.1.md`.
- Build/verify uses the **published application wheel 2.4.1** with `python -I`;
  a source checkout is rejected by `scripts/release_library.py`.
- CI (Windows + Ubuntu): install released app → `pytest
  tests/test_library_release.py` → build native bundle → independent verify
  (`verify_library_release.py`, frozen routes + worker execution) → seed wheel
  → publish.
- Assets: `Operon-Library-v3.0.1-{Linux,Windows}.operon-library.zip`,
  `operon_builtin_library-3.0.1-py3-none-any.whl`, `SHA256SUMS.txt`,
  `verification-{ubuntu,windows}-latest.json`.
- `gh release create --latest=false`; the application release channel is not
  touched.

The application/backend stays at **3.0.0**; no frontend, protocol v3 or
`export_results` contract change is part of this patch.

## 13. Reproduction

```bash
cd <repository root>
python -m operon registry check
python scripts/build_operator_docs.py --check
pytest -q tests/test_extension357.py tests/test_extension358.py \
          tests/test_extension11.py tests/test_extension280.py
pytest -q tests/test_export_results.py tests/test_export_contract.py
pytest -q tests/test_builtin_routes.py tests/test_route_combinations.py
pytest -q                     # full suite, log /tmp/full_pytest_301.log
git diff --check
```

Route reproduction:

```bash
python scripts/run.py library/seed/routes/<route> --check
python scripts/run.py library/seed/routes/<route> --memory-mb 512
# Hi-C (overlay): PATH=/tmp/hicenv/bin:$PATH PYTHONPATH=$PWD
# single_cell: --memory-mb 16384
```

Evidence:

| Path | Content |
| --- | --- |
| `/tmp/op_inventory.json` | 717-row operator inventory |
| `/tmp/verify/export_form/result.json` | 34 Form-export checks |
| `/tmp/verify/export_file/result.json`, `t2_afterfix.log` | FileArtifact/native producers, post-fix rerun |
| `/tmp/verify/genome/result.json` | antiSMASH/Rfam/tRNAscan/AMRFinder/Flye/QUAST |
| `/tmp/verify/omics_sc/result.json` | PBMC3k, loom, QIIME |
| `/tmp/verify/omics_tx/result.json` | DE, GWAS, meta-analysis, PRS, proteomics |
| `/tmp/verify/rna_seq/result.json` | RNAfold/duplex/cofold, protein properties, FASTA |
| `/tmp/verify/design/result.json` | ProteinMPNN, ESMFold, Boltz |
| `/tmp/verify/structure/ops_raw.json`, `run_ops_afterfix.log` | 1MEL operators, post-fix |
| `/tmp/verify/hic/result_envfix.json` | three Hi-C routes + export round-trip |
| `/tmp/verify/routes_csv/*.result.json` | 10 route runs |
| `/tmp/verify/gtf_fix/` | GTF route 8/8 |
| `/tmp/full_pytest_301.log` | full-suite log |

## 14. Final gates

Run on the release tree (library 3.0.1) on 2026-11-05.

| Gate | Command | Result |
| --- | --- | --- |
| Static registry | `python -m operon registry check` | 717 operators / 101 Readers / 7 packages / 24 routes; `errors []`; 108 pre-existing parameter-read warnings |
| Operator docs | `python scripts/build_operator_docs.py --check` | `changed []`, `errors []` |
| Packaging group | `pytest -q tests/test_packages.py tests/test_release_build.py tests/test_release_agent_harness.py tests/test_library_release.py` | 26 passed in 93.64s (0:01:33) |
| Full suite | `pytest -q -rs` | 2873 passed, 220 skipped, 48 warnings in 1721.03s (0:28:41) |
| Whitespace | `git diff --check` | clean |
| Windows launcher check | `python -m pytest` (Windows 3.12.10) on `tests/test_extension350.py`…`test_extension356.py` + `tests/test_export_results.py` | 50 passed, 7 skipped; `tests/test_extension357.py` + `test_extension358.py`: 11 passed, 4 skipped |
| Tag CI (final) | GitHub Actions run `42039684667` for `library-v3.0.1` | verify (ubuntu-latest) success, verify (windows-latest) success, publish success; assets: Linux bundle 20,178,876 B, Windows bundle 20,178,382 B, seed wheel 3,964,117 B, `SHA256SUMS.txt`, `verification-ubuntu-latest.json`, `verification-windows-latest.json`; both verification records report `passed: true`, 717 operators, 101 Readers |

The full suite ran once on the final 3.0.1 tree with `-rs`. It reports 220
skipped; the table below aggregates the 200 `SKIPPED` lines (parameterized
cases are counted once per line in the table). Every skip is an environment
gate: missing optional packages, unset real-tool flags, or absent
GPU/weights. Nothing is skipped because of a failure, and no test failed.

| Count | Skip reason |
| --- | --- |
| 42 | Rscript is not available |
| 38 | Rscript not available |
| 28 | Rscript not found |
| 6 | ESM-IF checkpoint or dependencies missing |
| 5 | Rscript is unavailable |
| 5 | Rscript unavailable |
| 4 | could not import 'allel': No module named 'allel' |
| 4 | could not import 'hictkpy': No module named 'hictkpy' |
| 4 | fair-esm is shadowed by the ESM-3 package |
| 3 | set OPERON_ESM3_REAL=1 to run the real ESM-3 check |
| 2 | Rscript is required |
| 2 | Set OPERON_HIC_REAL=1 in the Linux Hi-C environment |
| 2 | could not import 'linearmodels': No module named 'linearmodels' |
| 2 | could not import 'pysam': No module named 'pysam' |
| 2 | set OPERON_LIGANDMPNN_PATH and OPERON_LIGANDMPNN_WEIGHTS for the official oracle |
| 2 | set OPERON_REAL_ASSEMBLY=1 |
| 1 | OPERON_ANTIFOLD_WEIGHTS is not set |
| 1 | OPERON_ESM_CHECKPOINT is not set |
| 1 | OPERON_PFAM_HMM or hmmscan is not available |
| 1 | ESM-IF checkpoint or deps missing |
| 1 | Rscript is not installed |
| 1 | Windows Job Object lifecycle |
| 1 | could not import 'dendropy': No module named 'dendropy' |
| 1 | could not import 'mrcfile': No module named 'mrcfile' |
| 1 | could not import 'mudata': No module named 'mudata' |
| 1 | could not import 'pgenlib': No module named 'pgenlib' |
| 1 | could not import 'pyBigWig': No module named 'pyBigWig' |
| 1 | got empty parameter set for (task_path) |
| 1 | local ProteinMPNN checkout is not configured |
| 1 | official DockQ binary was built against NumPy 1.x |
| 1 | official LigandMPNN checkout or weights missing |
| 1 | official ProteinMPNN checkout or OPERON_RUN_PROTEINMPNN is absent |
| 1 | official ProteinMPNN checkout or weights missing |
| 1 | official ProteinMPNN checkout/weights or fixture unavailable |
| 1 | plink is not available |
| 1 | real SOP fixture is not present: tasks/bed_demo/input/example1.bed |
| 1 | real SOP fixture is not present: tasks/bgen_demo/input/example.bgen |
| 1 | real SOP fixture is not present: tasks/csv_demo/input/test_party_1.csv |
| 1 | real SOP fixture is not present: tasks/fasta_demo/input/sars_cov2.fasta |
| 1 | real SOP fixture is not present: tasks/gff3_demo/input/homo_sapiens.gff3.gz |
| 1 | real SOP fixture is not present: tasks/go_enrichment_demo/input/goa_human.gaf.gz |
| 1 | real SOP fixture is not present: tasks/h5ad_demo/input/pbmc3k.h5ad |
| 1 | real SOP fixture is not present: tasks/mtx_demo/input/matrix.mtx.gz |
| 1 | real SOP fixture is not present: tasks/multi_omics_route_demo/input/cite_seq_pbmc.h5 |
| 1 | real SOP fixture is not present: tasks/parquet_demo/input/alltypes.parquet |
| 1 | real SOP fixture is not present: tasks/plink2_demo/input/genotype.pgen |
| 1 | real SOP fixture is not present: tasks/plink_demo/input/genotype.bed |
| 1 | real SOP fixture is not present: tasks/vcf_demo/input/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz |
| 1 | set OPERON_AMRFINDER_REAL=1 to run the real AMRFinderPlus check |
| 1 | set OPERON_ANTIFOLD_REAL=1 to run AntiFold |
| 1 | set OPERON_ANTISMASH_REAL=1 to run the real antiSMASH check |
| 1 | set OPERON_ESM3_REAL=1 |
| 1 | set OPERON_ESM3_REAL=1 to run the ESM-3 SASA track |
| 1 | set OPERON_ESM3_REAL=1 to run the ESM-3 track |
| 1 | set OPERON_ESMFOLD_REAL=1 to run ESMFold 3B |
| 1 | set OPERON_ESM_CHECKPOINT to a local esm2_t6_8M_UR50D.pt |
| 1 | set OPERON_FOLDSEEK_BIN and OPERON_FOLDSEEK_DB to run the real search |
| 1 | set OPERON_OPENFOLD_REAL=1 for a real OpenFold run |
| 1 | set OPERON_OPENMM_REAL=1 for a real trajectory |
| 1 | set OPERON_PRODIGAL_REAL=1 to run the real Prodigal check |
| 1 | set OPERON_REAL_CRISPR=1 |
| 1 | set OPERON_RFAM_REAL=1 to run the real Rfam scan |
| 1 | set OPERON_RUN_PROTEINMPNN=1 with a local ProteinMPNN checkout |
| 1 | set OPERON_TRNA_REAL=1 to run the real tRNAscan-SE check |
| 1 | torch_scatter is ABI-incompatible: Could not load this library: <env>/lib/python3.12/site-packages/torch_scatter/_scatter_cpu.so |

The Windows run reproduced the CI failure (`tests/test_extension355.py::test_run_with_fake_quast`, `WinError 193`) before the launcher fix and passes after it. The frozen-route set exercised by `scripts/verify_library_release.py` is the same 350–356 set. The tag CI rerun (run `42039684667`) passed on both platforms and published the release, so the platform gate is closed.
