# BioPipe Operator Library 3.0.1 - Remote Cluster Verification

Date: 2026-11-06 (Asia/Shanghai). Workdir: /public/home/lihj/biopipe-verify-301.
Scope: dynamic smoke execution of the full operator catalog plus real-weight ESM runs and
domain batteries (structure, sequence, omics, MD). Read-only with respect to the repository.

## 1. Environment

| Item | Value |
|---|---|
| Repository | github.com/lovegavin/BioPipe, commit 740bd860 (public clone) |
| Library | biopipe_builtin_library-3.0.1-py3-none-any.whl, 3,964,117 B |
| Registry | 717 operators / 101 Readers / 7 packages / 24 routes, errors [] |
| Runtime | managed app 1.125.3 (Python 3.11.18, torch 2.6.0+cu124), isolated venv-esm2 |
| ESM stack | fair-esm 2.0.0 in esm_pkgs, openfold sm75 extension, dm-tree 0.1.10 (py311), torch_geometric 2.8.1, torch_scatter 2.1.2+pt26cu124 |
| ESM3 | /public/home/lihj/envtest2/esm3 (Python 3.12, esm 3.2.2, CPU) |
| Nodes | master 56c/251G/3090; node78 52c/480G/2080Ti 11G; node79 52c/2x3080; node80 avoided |
| Tools | tools/bioconda/bin: RNAfold, RNAduplex, mkdssp 4.2.2, prodigal, fpocket, hmmer |

All writes stayed under /public/home/lihj; no deletions were performed.

## 2. Method

- `biopipe operators list --view full` exported all 717 descriptors to logs/ops_full.json.
- harness families: numeric/statistics/ML (harness_num4.py), structure/sequence/omics
  (harness_dom.py), tools (tools_battery.py), ProteinMPNN (mpnn_family.py), MD (md_battery.py),
  ESM (esm_battery.py, esm_if_battery2.py, esm3_battery.py, esmfold_smoke.py).
- Each operator ran with a synthetic but contract-shaped Form (shared sample labels, correct
  arity/dims/labels, protein or DNA sequence_codes, real 1MEL structure for structure ops).
- Per-operator isolation (fresh Context/temp dir); budget 45-60 s. JSONL rows: id/status/elapsed/error.
- A status is `ok` only when run() completed and steps were written; timeouts and skips are separate.

## 3. Coverage result (merged, logs/coverage_final.json)

**603 / 717 executed successfully (84.1%)**; 101 error; 13 skipped; 0 timeout.

| Category | ok | error/skip |
|---|---|---|
| Statistics | 256 | 5 error |
| Machine Learning | 191 | 33 error |
| Omics | 57 | 0 |
| Structure | 41 | 12 skip |
| Sequence | 20 | 1 skip |
| Data | 11 | 5 error |
| Genome | 0 | 7 error |
| analysis | 5 | 8 error |
| data curation (数据整理) | 6 | 10 error |
| visualization (可视化) | 7 | 6 error |
| statistical analysis (统计分析) | 5 | 7 error |
| Quality control | 2 | 2+4 error |
| Docking | 1 | 2 error |
| Ligand / Antibody / Analysis | 0 | 1 each |

Raw category table and top errors: logs/coverage_final.json. Per-batch logs: cov_b, cov_dom,
cov_num..cov_num4_final, plus battery logs.

## 4. Real-weight ESM results (node78 2080 Ti unless noted)

| Operator | Result |
|---|---|
| esmfold_predict | 33 aa, mean_pLDDT 80.52, 21,708 B PDB, result_files registered |
| esm_if_score | 1MEL chain A, 132 residues, mean_log_prob -1.168051, total -154.182785, 16.3 s |
| esm_if_mutation_scan | 57 mutations over 3 positions, 3.6 s |
| esm_if_design | 2 designs, T=0.1, mean_recovery 0.643939, 9.9 s |
| esm_embedding | dim 1280, 3 sequences |
| esm_pseudo_likelihood | 125 positions, mean_log_prob -0.786221, total -98.277647 |
| esm_variant_effect | 57 mutations, 3 positions |
| esm3_* (5 ops) | embedding/SS/fold/inverse folding/generation all ok on CPU |

## 5. ProteinMPNN, MD and tool batteries

- ProteinMPNN: 13/28 ok (design, interface design/redesign, multi-model consensus, noise
  robustness, omit design, perplexity, probability profile, bias scan, native recovery scan,
  temperature ladder, bias matrix, masked design). Remaining errors are harness parameter
  wiring (proteinmpnn_path, num_seq_per_target, inputs) or missing v_48_002 weights.
- MD: 13/18 ok on a synthetic 40-frame trajectory (PCA, TICA, Markov states, free-energy
  landscape, quasi-harmonic entropy, communication path, contact/SS/SASA occupancy, etc.).
  rotamer_states/salt_bridge_occupancy fail on the generated topology lacking chi1/charged atoms.
- RNA/tools: 9 ok (RNAfold, ensemble, accessibility, duplex, cofold, cofold ensemble,
  pocket detection, prodigal, motif scan).

## 6. Defects worth a 3.0.2 patch

Output-Form contract defects (reproducible, independent of environment):
1. cox_stuart - np.int64 not JSON serializable in export.
2. dca - metric labels [6] for 7 data rows.
3. var_model - equation labels 8-12 inconsistent with axis.
4. mantel - labels.statistic.p index 1 on axis size 1.
5. nestedness - labels.statistic.N.rows=1 on axis size 1.
Tool/version defects:
6. structure_dssp_segments passes `--output-format dssp` but mkdssp 4.2.2 emits mmCIF;
   parser expects legacy DSSP (also seen locally).
7. limma_de.py uses gamma_gen._digamma/_trigamma; SciPy 1.17 default path breaks.
8. gc_skew_profile default window_size=10000 rejects sequences <10 kb.
9. esm_masked_marginal fails on torch 2.6 weights_only=True with fair-esm checkpoints.
10. OpenMM releases the GIL, so SIGALRM budgets do not interrupt minimization.

## 7. Remaining gaps (101 errors)

- External binaries/weights absent on the cluster: LigandMPNN (4), ESM checkpoints for
  some esm_* ids (12, covered manually here), structure predictors (14), tRNAscan/antiSMASH/
  AMRFinder/flye/quast/minced.
- Harness semantics for some ML estimators (typed array params, two-level factors, column
  names, multi-chain sequence labels) - 30+ ids, not product defects.
- The five Form defects above.

## 8. Evidence index

| Path | Content |
|---|---|
| logs/ops_full.json | 717 descriptors |
| logs/coverage_final.json | merged status + category table |
| logs/cov_b.jsonl, cov_dom.jsonl, cov_num*.jsonl | per-batch results |
| logs/esm_if_battery4.log | ESM-IF three-operator results |
| runs/esmfold_smoke/output/... | ESMFold PDB + step JSON |
| logs/md_battery.log, md_fix.log | MD batteries |
| logs/fix3.log | ProteinMPNN parameter fixes |
| REPORT_NUM4.md, REPORT_DOM.md | sub-agent reports |
| BIOPIPE_REMOTE_ASSETS.md | AF2/RFantibody/ESM resource locations |
