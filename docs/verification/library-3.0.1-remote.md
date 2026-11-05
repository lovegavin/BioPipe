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

## 9. 24-route end-to-end verification (real data)

The 24 built-in routes were executed on `master` / `node78` with the official
classic datasets in `data/` (manifest: `data/MANIFEST.json`, 20 files with URL,
bytes and sha256). Composite result: **19 complete / 5 skip**. Per-route evidence
is in `ROUTES_E2E.jsonl` (16 routes), `ROUTES_HIC.jsonl` (3), `ROUTES_STRUCT.jsonl`
(14 structure/docking graphs) and `ROUTES_GENOME.jsonl` (genome graphs), with
`--check` results in `evidence/check_status.json`.

| route | status | steps | elapsed (s) | classic data |
|---|---|---|---|---|
| single_cell | complete | 14 | 298.07 | 10x PBMC3k |
| interval_analysis | complete | 9 | 66.87 | ENCODE cCREs + Ensembl regulatory |
| rnaseq_de | complete | 12 | 62.13 | Bioconductor airway |
| go_enrichment | complete | 5 | 26.32 | GOA human GAF |
| single_cell_loom | complete | 11 | 10.13 | bundled |
| survival | complete | 5 | 7.86 | TCGA-BRCA (Xena/GDC) |
| microbiome | complete | 22 | 6.85 | QIIME moving-pictures |
| single_cell_batch | complete | 7 | 4.48 | bundled |
| gwas | complete | 16 | 3.58 | 1000G chr22 subset |
| rnaseq_de_enrichment | complete | 7 | 3.19 | bundled |
| sequence_features | complete | 9 | 2.53 | Ensembl yeast chr I |
| proteomics_limma | complete | 7 | 2.02 | bundled |
| microbiome_diff | complete | 8 | 1.93 | bundled |
| rnaseq_ssgsea | complete | 6 | 1.48 | bundled |
| gtf_annotation | complete | 8 | 1.35 | Ensembl yeast GTF |
| gwas_meta_prs | complete | 4 | 0.17 | bundled |
| hic_pairs | complete | 7 | 338.20 | open2c/cooler Aag2 pairs |
| hic_fastq | complete | 10 | 48.74 | S. cerevisiae chrI synthetic reads |
| hic_bam | complete | 8 | 31.84 | same reads, bwa mem -5SP BAM |
| bgen_qc | skip | - | - | reader defect (below) |
| ml_classification | skip | - | - | msdata has no protein x sample matrix |
| ml_regression | skip | - | - | same data gap |
| proteomics_de | skip | - | - | same data gap |
| multi_omics | skip | - | - | 10x CITE-seq H5 (HTTP 403) |

Hi-C export round trip: exported `.hic` re-read with hictkpy 1.4.0 (24 bins,
296 nnz, sum 28,209, res 10,000) and `hictk validate` -> valid; exported `.cool`
re-read with cooler 0.10.4 (24 bins, nnz 296, sum 28,209, symmetric-upper) and
sha256-identical to the route's `contacts.cool`; CSV parse-checked 24x25
(100x101 for pairs). The `.hic` writer scales with chromosome count: the
3,579-contig/173,971-bin pairs matrix stalls (>15 min, 7.6 GB RSS; `hictk
convert` shows the same), so that route exports cool+csv and the `.hic`
roundtrip is evidenced on the 24-bin routes. This is a writer-scaling
limitation, not a BioPipe defect.

Known skip defect: `bgen_qc` with a plink2 BGEN. `bgen-reader` returns
`(2504, 648, 4)` one-hot 2-bit planes instead of `(..., 3)`; dosage
`P(AB) + 2*P(BB)` reaches 3.0 and the output contract rejects it
(`invalid allele_count value np.float32(3.0)`). The official example BGEN host
returned 403, so this is reproducible only with a locally generated plink2 file.

## 10. Genome routes with official tools (real data)

Seven genome routes were authored under `runs/route_genome_*` (task.yaml +
parameters.json + input/), passed `--check`, and ran end-to-end with the
official binaries installed under `tools/envs/`; every route ends in a
non-plotting `export_results`. Evidence: `ROUTES_GENOME.jsonl` (7 lines) and
`SUMMARY_GENOME.md`.

| route | tool | elapsed (s) | key numbers | oracle |
|---|---|---|---|---|
| antismash | antiSMASH 8.0.4 + DB | 13.35 | nisin 15,016 bp, 1 region 1-15,016 lanthipeptide-class-i, 12 genes, 1 protocluster; export 1 row | CLI JSON same region/product/12 CDS PASS |
| amrfinder | AMRFinderPlus 4.2.7 + DB 2026-10-29.1 | 107.15 | E. coli K-12, 0 hits (negative control) | CLI 0 hits PASS |
| amrfinder_pos | AMRFinderPlus 4.2.7 | 1.61 | pBR322, 2 hits tet(C) 86-1273, blaTEM-1 3296-4153 (100% id/cov) | CLI identical PASS |
| trna | tRNAscan-SE 2.0.13 | 36.46 | 89 tRNAs, 24 isotypes; export 89 rows | CLI 89 tRNAs, 0 coordinate mismatches PASS |
| flye | flye 2.9.6 | 115.48 | 291 x 5 kb, 3% error lambda reads (30x); 1 contig 48,502 bp, N50 48,502, circular | QUAST 5.3.0 48,502 bp, 100% fraction, 0 mismatches PASS |
| assembly_stats | QUAST 5.3.0 | 1.12 | 54 metrics on the Flye FASTA + reference; N50 48,502, 100% fraction | 53 numeric metrics equal PASS |
| crispr | minced 0.4.2 | 7.85 | K-12, 2 arrays (2,877,701-2,878,463 13 repeats 29/32; 2,904,014-2,904,407 7 repeats 28/33) | CLI identical spans/repeat counts PASS |

Notes: antiSMASH needs an explicit `database_dir`; `rfam_scan` was not run
because no pressed Rfam.cm / Infernal database exists in this workspace
(tRNAscan-SE covers the tRNA item); Flye emits contig statistics but no
sequences in its output Form, so `assembly_stats` is a separate route over the
exported FASTA; the venv used for these runs reports `biopipe 3.0.0`.

## 11. Family coverage graphs (real data)

Nine additional family graphs under `coverage/graphs/` (six wave-1 + three
rescue) exercise operators that the 24 built-in routes do not touch:
tab_stats (67 steps/189.0 s), tab_ml (44/28.6 s), struct (16/67.2 s), omics
(16/1.6 s), seq (14/9.4 s), data (9/6.0 s), w2_struct (8/5.8 s), w2_seq
(5/1.2 s), w2_data (3/0.04 s). Totals: 182 executed step records, 165 distinct
operators (164 analysis + export_results), each in exactly one graph, zero
overlap with the 87 operators of the built-in routes and zero overlap between
graphs. Framework-tested operators overall: 87 + 165 = 252/717; the remaining
465 have per-op reasons in `coverage/UNCOVERED.md` (369 bind-sweep errors, 91
unbound, 5 graph-step errors below).

Every graph ends with `export_results` on the terminal real-data Form plus one
intermediate export: 18 exports (9 terminal + 9 intermediate), all files exist
and read back, sha256 recorded; all 9 terminal exports are value-equal to the
declared source Form (`max_abs_diff 0.0`; 14,448 values for golub_wide, 26,180
for biom_qiime). Intermediate exports carry read-back + sha256 only because
there is no reference Form for those operator outputs (`values_match: null`).
Evidence: `coverage/COVERAGE_ROUTES.jsonl`,
`coverage/ROUTE_OPERATOR_MATRIX.csv` (48 rows x 256 operator columns),
`coverage/builtin_candidates/` (9 staged routes) and per-graph
`README.md`/`graph.mmd`/`input_manifest.json`.

A library defect surfaced only inside graph runs: `src/task/step/base.py`
declares `@classmethod estimate_memory(cls, inputs, params, profiles)` returning
`(workspace, output)`, but eight step modules define an instance method that
returns a dict; five surface in these graphs, so the planner calls it with the wrong arity
(`missing 1 required positional argument: 'profiles'`). Affected operators
include `esm_embedding_outlier_scan`, `structure_cavity_scan`,
`sequence_kmer_profile`, `sequence_gc_profile` and `structure_helix_geometry`. This is a 3.0.2 fix
item; the repo was not modified here.

`bgen_qc` remains the other reader-level 3.0.2 item: plink2 BGEN is decoded as
four one-hot planes, so dosage reaches 3.0 and the output contract rejects it.

## 12. `estimate_memory` contract fix (3.0.2 candidate)

The graph planner calls `Step.estimate_memory(inputs, params, profiles)` as a
class method returning `(workspace_bytes, output_bytes)`. Ten step modules
declared an instance method that ignored `profiles` and returned a dict
(`{"full": ...}` / `{"bytes": ...}`) or a bare int. Planning those nodes in a
graph failed before execution with:

```
estimate_memory() missing 1 required positional argument: 'profiles'
```

Affected: `esm_embedding_outlier_scan`, `esm_if_masked_region_scan`,
`esm_if_mutation_scan`, `proteinmpnn_interface_redesign`,
`proteinmpnn_native_recovery_scan`, `proteinmpnn_perplexity`,
`rdkit_pharmacophore_features`, `rdkit_scaffold_diversity`,
`sequence_gc_profile`, `structure_helix_geometry`.

Fix: each is now `@classmethod` with the base signature and returns
`(estimate, 0)`, preserving the previous byte estimate as the workspace
reservation. `tests/test_extension359.py` asserts the decorator and the
two-int return for all ten (plus the two inheriting steps).

Evidence (local `biopipe` env, library tree at commit 018fb29b + fix):

| stage | result |
| --- | --- |
| before | `pytest tests/test_extension359.py` -> 12 failed |
| after | `pytest tests/test_extension359.py` -> 12 passed |
| focused regression | 357 + 358 + 359 + export_results -> 51 passed |
| registry | 717 operators / 101 Readers / 7 packages / 24 routes, errors [] |

Remaining 3.0.2 candidates from this verification: `bgen_qc` reader dosage
(`invalid allele_count value 3.0`), five Form label defects (`cox_stuart`
int64 serialization, `dca`, `var_model`, `mantel`, `nestedness`), DSSP
parsing of mkdssp 4.x mmCIF output, `limma_de` on SciPy 1.17
(`gamma_gen._digamma`), `gc_skew_profile` 10 kb default window, and
`esm_masked_marginal` under torch 2.6 `weights_only=True`.
## 13. Five Form-boundary defects

Remote framework runs exposed five operators whose declared output Form did
not satisfy the runtime label contract. The failing stage was output
validation, not the statistical computation; the new
`tests/test_extension360.py` reproduces each case without any external tool.

| Operator | Defect | Fix |
| --- | --- | --- |
| `cox_stuart` | `n_pairs` stayed `numpy.int64`, so exporting the step raised the JSON serialization error | cast to `int` before export |
| `dca` | rows carried seven values (threshold first) while only six metric labels exist, so the output Form failed validation | drop the threshold column; thresholds remain in the `threshold` dim |
| `var_model` | block shape `(neqs*terms, 4)` but labels were `equation=neqs` and `term=terms` | label `equation` with the six `equation:term` rows and `term` with `coef/se/t/p` |
| `mantel` | statistic row vector `(1, 4)` while four labels were declared | return a `(4, 1)` column vector |
| `nestedness` | same `(1, 4)` row vector with four labels | return a `(4, 1)` column vector |

Evidence: before the change, `pytest tests/test_extension360.py` produced
`5 failed`; after it, `5 passed`. The three legacy unit tests that asserted
the old shapes (`tests/test_extension8.py`, `tests/test_extension80.py`,
`tests/test_extension99.py`) were updated to the corrected contract, and the
combined regression set finished with `47 passed, 6 skipped`. `registry
check` still reports `717 operators / 101 Readers / 7 packages / 24 routes`
with `errors []`. These five defects, together with the earlier
`estimate_memory` contract fix, belong to the 3.0.2 patch candidate set.

## 14. Reader/tool portability fixes (BGEN 4-plane, DSSP PDB fallback)

Two defects were reproduced from the remote cluster and fixed in the library.

### 14.1 BGEN reader: four-plane haplotype probabilities

Remote `runs/route_bgen_qc/input/example.bgen` opened with `bgen_reader 4.0.9`
returns `(2504, 648, 4)`: one-hot probabilities per haplotype
(`[hap1 A, hap1 B, hap2 A, hap2 B]`, each haplotype sums to one).  The reader
assumed the three-plane layout and computed `P(AB) + 2 P(BB)`, yielding
`3.0` and a contract rejection:

```
StepError: invalid allele_count value np.float32(3.0)
```

Fix: when four planes are present, dosage is `P(hap1 B) + P(hap2 B)`; a
haplotype with both allele probabilities zero marks the genotype missing.
The three-plane path is unchanged.

### 14.2 DSSP: mkdssp 4.6 rejects some valid PDB files

`mkdssp 4.6.1` on `tests/fixtures/vhh_1mel.pdb` exits 1:

```
parse error at line 1: This file does not seem to be an mmCIF file
>> Duplicate Key violation, cat: refine values: B_iso_mean
```

The same file is accepted by `mkdssp 4.2.2`; the same 4.6.1 binary accepts
`1MEL.cif`.  `structure_dssp_segments` now retries once after converting a
`.pdb/.ent` input to mmCIF with Biopython `MMCIFIO`.  If Biopython is absent
or conversion fails, the original DSSP error is preserved.

### 14.3 Regression evidence

`tests/test_extension361.py` contains three tests: four-plane dosage,
three-plane dosage, and the PDB->mmCIF retry (subprocess mocked).

```
before: 2 failed, 1 passed in 0.14s
after:  3 passed in 0.11s
focused suite (357-361, export_results, old five-form tests,
mantel/dca/var_model, DSSP): 89 passed, 1 skipped in 3.81s
```

## 15. BGEN route completes after the four-plane fix

The built-in `bgen_qc` route previously stopped at the first reader:

```
reader BgenReader output contract: invalid allele_count value np.float32(3.0)
```

With the reader fix from section 14.1 installed (library built from main
`59b4e5cb`, registry 717/101/7/24, errors `[]`), the same route directory with
the official `example.bgen` (2504 samples x 648 variants) now completes:

```
status: complete, 8/8 steps, total_elapsed 6.0098 s,
managed_peak_bytes 13,431,817
maf -> ld_prune (1.935 s) -> pca (2.816 s, PC1 0.081, PC2 0.050)
 -> scatter (1.008 s) -> describe 210 x 2504, n_valid 525840
```

This supersedes the `bgen_qc` row of section 9: the built-in route tally is
now **20 complete / 4 skipped** (remaining skips: ml_classification,
ml_regression, proteomics_de lack a protein x sample matrix; multi_omics
requires a CITE-seq H5 that returned 403).

## 16. DSSP route completes on mkdssp 4.6.1 via the mmCIF fallback

Section 14.2 showed that `mkdssp` 4.6.1 rejects the repository fixture
`tests/fixtures/vhh_1mel.pdb` with a `parse error`/`Duplicate Key` message.
The fixed step was exercised end-to-end through the task runner on the same
binary:

```
env PATH=$PWD/tools/bioconda/bin:$PATH \
  venv/bin/python repo/biopipe/scripts/run.py runs/route_dssp_fix --memory-mb 4096
```

```
status: complete, 2/2 steps, total_elapsed 5.1062 s, managed_peak 914,432 B
structure_dssp_segments: n_segments 187, n_residues 518
export_results: dssp_segments.csv, 3,735 B, 188 rows
header: segment,length
first:  A:coil[2-2],1.0
last:   M:coil[127-127],1.0
```

Direct `mkdssp 4.6.1 --output-format dssp` on that PDB still exits 1, so the
success proves the PDB -> mmCIF conversion and single retry ran in the real
worker, not a different binary or input.

## 17. Protocol v3 assessment: operator defects vs SDK hardening

The question was whether the defects found in this campaign indicate a v3
protocol problem. Short answer: **no v3 definition/parameter/contract grammar
violation was found.** Every affected operator still passed registry
validation (`717/101/7/24`, errors `[]`), and its `definition`/parameters JSON
was structurally valid. The failures are at three other layers.

| Layer | Examples | Verdict |
|---|---|---|
| Operator implementation vs its own output contract | five Form defects (`cox_stuart`, `dca`, `var_model`, `mantel`, `nestedness`) | operator bug: the produced Form did not match the labels/orientation the operator itself declared |
| Reader decode | `BgenReader` treated a four-plane haplotype encoding as three-plane dosage and emitted 3.0 | reader bug; the output contract correctly rejected the out-of-range value |
| External tool / third-party API | mkdssp 4.6.1 rejects the fixture PDB; `limma_de` calls SciPy-private `gamma._digamma/_trigamma` | tool-version / private-API fragility, not protocol |

Two SDK/protocol hardening items are worth a collaborator change, because
they let these bugs ship silently:

1. **`estimate_memory` is an undocumented-in-protocol hook.** It is described
   in `docs/step_extensions.md` as
   `estimate_memory(inputs, params, profiles)`, and the planner requires a
   classmethod returning `(workspace, output)`, but the v3 `definition` has no
   field for it and registry build does not inspect it. Ten operators shipped
   instance methods with dict/int returns and only failed at planning time with
   `estimate_memory() missing 1 required positional argument: 'profiles'`.
   Suggested enforcement: at plugin load (or registry build), assert
   `inspect.getattr_static(cls, "estimate_memory")` is a `classmethod`, that
   the signature accepts `(inputs, params, profiles)`, and that a probe call
   with `({}, {}, {})` returns a 2-tuple of non-negative numbers. Cross-link
   the hook from `docs/operator_protocol.md`.
2. **No generic output-Form assertion before export.** Contracts declare output
   dims/labels, but the runner does not verify that the returned Form's axis
   sizes match its label maps and contract dims, nor that exported scalars are
   JSON-safe. The five Form defects and the `np.int64` export failure would
   have been caught at step completion instead of at a later export/consumer.
   Suggested enforcement: validate `form.dims`, per-axis `len(labels)` and
   `Form.validate()` on every declared output; optionally reject non-JSON
   scalar types in `Step.export()`.

Neither change alters v3 syntax or existing workflow files; both are
registration/runtime checks plus documentation. The reader-side BGEN fix and
the DSSP mmCIF fallback remain operator/library fixes (sections 14-16), and the
`limma_de` private-SciPy dependency should be replaced with
`scipy.special.polygamma` in a follow-up (not changed here).

## 18. `limma_de` moved off SciPy-private gamma helpers

`limma_de._prior` estimated the empirical-Bayes prior with
`scipy.stats.distributions.gamma._digamma` / `._trigamma`, private helpers that
are absent in current SciPy (local 1.18.1 and the remote 1.17 build):

```
AttributeError: 'gamma_gen' object has no attribute '_digamma'
```

This only triggers when `prior_df` is not supplied (automatic prior), which is
why the fixed-`prior_df` route run did not expose it. The implementation now
uses the public `scipy.special.digamma` and `scipy.special.polygamma(1, x)`;
no formula or output contract changed.

Evidence (fail first, then pass):

```
pytest tests/test_extension362.py
  2 failed in 0.49s        # AttributeError + private-helper source check
pytest tests/test_extension362.py tests/test_extension_operators.py \
  -k "limma or prior or scipy"
  3 passed, 9 deselected in 0.53s
```

The regression test exercises `_prior(..., prior_df=None)` on a six-feature
variance vector and asserts a finite positive prior, and it rejects any
remaining `stats.distributions.gamma._*` reference in the module source.
Library registry was rebuilt after the change; no v3 definition, parameter or
contract file was touched.

## 19. Post-fix route retests

Per the test-later rule, routes that ran before a library fix are rerun once the
fixed commit is deployed. The remote repo was advanced to `a78652bc` (public
SciPy gamma helpers) and rechecked:

| route | before | after | evidence |
| --- | --- | --- | --- |
| `proteomics_limma` | complete (private SciPy path) | complete, 7/7 steps | `runs/route_proteomics_limma/output/run_summary.json` |

`--check` returned `CHECK OK`; the rerun overwrote the same route output and
kept the same graph, parameters and data. Routes unaffected by a fix are not
rerun (test-later rule).

## 20. Second coverage wave (wave-3 graphs)

A second solver wave added 11 real-data task graphs (`g2_*`, `g3_*`, `g4_fixed`)
under `coverage/graphs/`, executed with `scripts/run.py --memory-mb 4096`.

| graph | ops | steps ok | elapsed s |
| --- | --- | --- | --- |
| g2_data | 4 | 6 | 0.07 |
| g2_omics | 14 | 16 | 4.68 |
| g2_struct | 2 | 4 | 3.49 |
| g2_tab_ml | 16 | 18 | 1.42 |
| g2_tab_stats | 83 | 85 | 5.92 |
| g3_data | 1 | 2 | 0.05 |
| g3_omics | 1 | 3 | 0.38 |
| g3_struct | 2 | 4 | 0.55 |
| g3_tab_ml | 5 | 7 | 1.07 |
| g3_tab_stats | 1 | 2 | 4.65 |
| g4_fixed | 5 | 7 | 19.51 |

Totals: **11/11 graphs complete, 154 operator steps ok, 3 dropped, 134 distinct
new operators**, zero overlap with the wave-1 operators and zero with the
builtin routes; no operator appears in more than one wave-3 graph.

- Cumulative framework coverage: **386/717 (53.8%)** = builtin 87 + wave-1
  164 + wave-3 134.
- The 5 `estimate_memory` operators re-ran green on current HEAD `a78652bc`
  (`g4_fixed`, 7 steps, 19.5 s): the earlier failure was a stale working tree,
  not the fixed commit.
- Dropped: `fligner_killeen` (no feature had two finite values in every group),
  `manova` (residual covariance is singular), `difference_sign` (needs two
  non-zero successive differences). These are data-shape limits, not crashes.
- 20 export artifacts across wave-3 graphs exist and were read back
  (`WAVE2_EXPORTS.json`, every `readback_ok=true`), with sha256 and row/col
  counts.
- Evidence: `coverage/WAVE2_ROUTES.jsonl` (graph rows with explicit operator
  arrays + per-op rows), `WAVE2_SUMMARY.md`, per-graph `task.yaml`,
  `parameters.json`, `graph.mmd`/`graph.dot`, `README`, and
  `_exec/<graph>/output/run_summary.json`; refreshed `UNCOVERED.md` (331
  remaining, wave-1 copy kept as `UNCOVERED.wave1.md`) and
  `ROUTE_OPERATOR_MATRIX.csv/json` (39x717).

Remaining 331 uncovered operators break down as: 205 one-off StepErrors, 52
small-n (need >=8..302 complete observations while the 48-sample source is too
small for some), 23 arity/harness (descriptor arity differs from the class
arity), 18 label/column, 16 unbound (no contract-matching real source), 14
sequence/structure contract, 3 singular/non-positive.

Caveat: a few bindings are contract-valid but semantically distant (for example
`topic_lda` on 48x1 metadata or `antibody_numbering_imgt` on a pBR322 FASTA).
The data and execution are real, but these rows are disclosed as coverage
evidence, not as domain-meaningful routes.

## 21. Final local gates

Run on the library tree at the commit that carries this report (`a78652bc` plus
documentation-only commits), after all fixes in sections 12-19:

| gate | command | result |
| --- | --- | --- |
| registry | `python -m biopipe registry check` | 717 operators / 101 Readers / 7 packages / 24 routes, `errors []` |
| operator docs | `python scripts/build_operator_docs.py --check` | `changed []`, `errors []`, 7 authored pages preserved |
| full suite | `python -m pytest -q -rs` | **2896 passed, 220 skipped, 0 failed** in 1730.80 s |
| packaging | `pytest tests/test_packages.py tests/test_release_build.py tests/test_release_agent_harness.py tests/test_library_release.py` | 26 passed in 93.64 s (section 14) |
| portability | `pytest tests/test_portability.py::test_active_source_has_no_developer_paths` | 1 passed |
| whitespace | `git diff --check` | clean |

The 220 skips are environment gates, not failures. The largest groups are the
120 R/limma oracles (`Rscript` is not installed on this host), 13 SOP fixture
cases, 10 `hictkpy` cases, ESM-IF/fair-esm/OpenFold/ProteinMPNN/Foldseek/OpenMM
opt-ins that need weights or dedicated environments, and a few optional
libraries (mrcfile, torch_scatter ABI, DockQ numpy pin, Windows Job Object).
The per-test reasons are in the `-rs` log written alongside this run.

## 22. Fourth coverage wave

Five more real-data graphs (`w4_data`, `w4_omics`, `w4_seq`, `w4_struct`,
`w4_tab_stats`) completed with rc=0 and zero dropped steps: **18 new distinct
operators**, zero real-operator overlap with the previous waves, cumulative
**403/717 (56.2%)**.

New operators: `barnard_test`, `bhapkar_test`, `boschloo_exact`, `cohens_h`,
`difference_sign`, `fisher_exact`, `flow_transform`, `indicator_species`,
`odds_ratio`, `ordinal_logistic`, `risk_ratio`, `sequence_isoelectric_point`,
`sequence_repeat_finder`, `structure_cation_pi`, `structure_contacts`,
`structure_plddt_profile`, `structure_ss_bridge_network`,
`stuart_maxwell_test`.

What unlocked them: scoring candidates against each Step class's real
`input_contracts` instead of descriptor arity, a 68-source pool with relabeled
views of real matrices (values unchanged), real protein/CDS FASTAs from repo
fixtures, and a 2x2 contingency table derived from the real Golub GCT. Ten
export files were produced; all read back, five terminal exports matched their
source Form at `max_abs_diff = 0.0`.

This wave missed its +40-80 target (+18). The remaining 313 uncovered operators
are bucketed as 102 arity/parameter harness gaps, 61 domain-specific semantics,
61 sequence/structure contract gaps, 33 label/column mismatches, 30 operators
needing more than 302 observations, 17 missing tool/data files, and 9 with no
contract-matching source. Hard workspace limits: no SMILES/openbabel, no MD
trajectories, no foldseek/vina/esm3/boltz binaries, and model-backed operators
stall on an aborted network fetch.

Evidence: `coverage/WAVE4_ROUTES.jsonl`, `WAVE4_SUMMARY.md`,
`WAVE4_EXPORTS.json`, refreshed `UNCOVERED.md` (313, bucketed) and
`ROUTE_OPERATOR_MATRIX.csv` (112x404); previous copies retained as `.wave3`.
