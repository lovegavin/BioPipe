# Backend versioning

This page defines how the **backend/application version** of BioPipe is managed.
It is the version in `pyproject.toml` and `biopipe/__init__.py`, reported by
`biopipe --version` and used by the generated plugin dependency bound.

## Independent version axes

| Axis | Owner | Declared in | Current |
| --- | --- | --- | --- |
| Backend application | backend maintainer | `pyproject.toml`, `biopipe/__init__.py` | **1.58.0** |
| Frontend / desktop package | frontend maintainer | `frontend/package.json` | 0.116.2 (independent) |
| Authoring protocol and SDK | protocol maintainer | `protocol_version` 3, `biopipe_sdk` 3.1.0 | v3 / 3.1.0 |
| Operator library bundle | release tooling | `.biopipe-library.zip` build | tracks a build, not this version |

A backend increment never silently changes the protocol version, the SDK version
or the frontend package version. A frontend release does not require a backend
increment unless it depends on new backend behavior, and a backend release does
not renumber the frontend.

## Rules

**MAJOR (X).** Milestone or architectural change, kept for long intervals. A
breaking change to backend behavior, plugin compatibility, or a removed/renamed
operator or Reader ID requires a MAJOR increment.

**MINOR (Y).** One increment per **expansion batch** that adds or removes
operators, Readers, providers or route templates. A batch gets exactly one MINOR
increment, even when it is delivered in several commits or contains several
capability families. Numbers are not skipped.

**PATCH (Z).** One increment per user-visible change set that does **not** expand
the library: bug fixes, refactors, documentation, tests, dependency or build
changes. PATCH is not used to publish new capabilities.

Examples:

```text
1.0.0  first backend release (protocol v3 integration)
1.1.0  expansion batch: five population-genetics operators
1.1.1  fix: a window edge case in an existing statistic
1.2.0  expansion batch: Arrow reader, seasonal decomposition and Fst-family statistics
1.3.0  expansion batch: Faith PD, UniFrac distances, patristic distance and PhyloXML
1.4.0  expansion batch: causal-inference operators and a MuData reader
1.6.0  expansion batch: SIMPER, MRPP, species accumulation and cophenetic correlation
1.7.0  expansion batch: Moran's I, indicator species, pairwise alignment and PDBML
1.8.0  expansion batch: PCoN-M, Cuzick trend test, Fisher's alpha and a TPED reader
1.9.0  expansion batch: MANOVA, quadratic discriminant analysis, k nearest neighbours and a logistic mixed model
1.10.0  expansion batch: exact Poisson tests, binomial confidence intervals, chi-square goodness of fit and redundancy analysis
1.12.0  expansion batch: Lilliefors, Cox-Stuart, Mann-Kendall rank and Pearson normality tests
1.13.0  expansion batch: Mood scale test, two-sample F test, D'Agostino skewness and Anscombe-Glynn kurtosis tests
1.14.0  expansion batch: linear discriminant analysis, simple correspondence analysis, nestedness and Rényi diversity
1.15.0  expansion batch: beta diversity (24 indices), Tsallis diversity, variation partitioning and a CCP4/MRC volume reader
1.16.0  expansion batch: bio-environment matching, Morisita index and NIfTI/NRRD volume readers
1.17.0  expansion batch: Nelson-Aalen, Gower distance, PAM and STL/OBJ mesh readers
1.18.0  expansion batch: OPTICS, BIRCH, HDBSCAN and PLY/OFF mesh readers
1.18.1  patch: normalize string paths in the PLY and OFF readers
1.19.0  expansion batch: ProteinMPNN design, ESM masked marginals, minibinder interface, ligand contact profiles, protein-aware FASTA and full-atom PDB columns
1.19.1  patch: pass POSIX-style paths to ProteinMPNN so sequence design runs on Windows
1.20.0  expansion batch: RDKit descriptors, Morgan fingerprints and SMILES standardization, ESM sequence embeddings, interface buried area
1.20.1  patch: make the ProteinMPNN path assertions platform-neutral so the focused suite is green on Windows
1.21.0  expansion batch: ProteinMPNN score-only scoring, antibody developability, ESM masked-marginal pseudo-likelihoods, RDKit Murcko scaffolds and a PDBQT reader
1.22.0  expansion batch: ESM variant-effect scans, interface-focused ProteinMPNN design, RDKit ADMET rules, RDKit conformer energies and Kabat-style antibody CDR annotation
1.23.0  expansion batch: Kabsch structure RMSD, interface hotspot profiles, RDKit similarity matrices, PAINS filter alerts and ligand efficiency metrics
1.24.0  expansion batch: solvent-excluded contact networks, backbone hydrogen bonds, maximum common substructures, and LigandMPNN ligand-aware design and scoring
1.24.1  patch: move the operator output metadata into open information so runner contract validation accepts the new forms
1.25.0  expansion batch: ESM-IF inverse-folding design and scoring, interface contact maps, CDR physicochemical profiles, and RDKit tautomer canonicalization
1.26.0  expansion batch: ESM-IF mutation scans, ESOL solubility, SMARTS match matrices, interface hydrophobic patches, and CDR hydrophobicity profiles
1.27.0  expansion batch: oral bioavailability rule sets, QED drug-likeness, per-residue SASA, and CDR liability motif scanning
1.28.0  expansion batch: ESM-IF partial redesign, Ertl synthetic accessibility, B-factor profiles, and sequence complexity metrics
1.29.0  expansion batch: interface atom-pair histograms, residue packing density, sliding-window hydrophobicity profiles, BRICS/RECAP fragment profiles, and ProteinMPNN conditional probability profiles
1.30.0  expansion batch: ProteinMPNN multi-model ensemble scoring, maximum common substructure clustering, interface hydrogen-bond networks, and PROSITE-style motif scanning
1.31.0  expansion batch: ProteinMPNN design-position entropies, ESM embedding PCA and nearest neighbours, disulfide bonds, and salt bridges
1.31.1  patch: default the ProteinMPNN designer interpreter to sys.executable so the operator starts on Windows
1.32.0  expansion batch: ProteinMPNN design-position profiles, amide-pi and cation-pi contacts, aromatic stacking, and RDKit conformer clustering
1.33.0  expansion batch: ESM-IF per-position entropy, LigandMPNN active-site design, ProteinMPNN amino-acid bias scans, and seeded random SMILES augmentation
1.34.0  expansion batch: CDR-fixed antibody framework redesign, multi-checkpoint ProteinMPNN consensus, ESM-IF binder-interface redesign, and ProteinMPNN temperature ladders
1.35.0  expansion batch: ProteinMPNN binder-interface redesign, ESM-IF sliding-window masked redesign, per-position native recovery, and RDKit pharmacophore feature counts
1.35.1  patch: copy the RDKit feature definition file to an ASCII path before building the pharmacophore factory
1.35.2  patch: reuse the ASCII-safe RDKit feature file in the pharmacophore oracle and drop multi-chain FASTA separators in the native-recovery scan
1.36.0  expansion batch: dihedral secondary structure segments, contact order, BRICS fragment overlap, and ProteinMPNN design diversity
1.36.1  patch: fall back to the repository vanilla_model_weights directory when no weights path is given
1.37.0  expansion batch: ProteinMPNN per-position perplexity, Murcko scaffold diversity, embedding outlier scan, nucleotide GC profile, helix geometry
1.38.0  expansion batch: side-chain chi angles, k-mer composition profiles, embedding PCA loadings, reaction SMARTS application, and restriction-site scans
1.39.0  expansion batch: per-residue surface hydrophobicity, six-frame ORF finding, Morgan atom-environment histograms, metal coordination shells, and CDR length profiles
1.39.1  patch: index metal shells with absolute atom positions so ions that are not the first atom are found
1.40.0  expansion batch: backbone dihedral and Ramachandran classes, CA distance matrices, ring-system statistics, charge profiles and ligand burial
1.40.1  patch: resolve the dihedral-oracle PDB fixture relative to the test module so it runs on Windows
1.41.0  expansion batch: helix-helix geometry, ligand steric clashes, Murcko scaffold fingerprints, embedding k-means silhouettes, and CpG island scans
1.42.0  expansion batch: helix bend profiles, halogen bond scans, ProteinMPNN design clustering, and spectral embedding projections
1.43.0  expansion batch: buried cavity scans, ligand residue contact maps, scaffold trees, and tandem repeat finding
1.44.0  expansion batch: masked ProteinMPNN design, secondary-structure bridge networks, SMARTS functional-group counts, and GC/AT skew profiles
1.44.1  patch: forward an explicit ProteinMPNN weights directory so masked design runs on Windows
1.45.0  expansion batch: codon adaptation index, cavity lining residues, CDR grafting, and interface-masked ProteinMPNN design
1.46.0  expansion batch: ProteinMPNN noise robustness, embedding linear probes, zinc coordination sites, and transmembrane segments
1.46.1  patch: skip water, ion and ligand rows when deriving the masked interface, so real PDB entries build a valid protein mask
1.46.2  patch: resolve catalog icons through the frontend registry and report a missing scikit-learn install as a step error
1.47.0  expansion batch: ProteinMPNN tied-residue design, spectral domain boundaries, ligand pose RMSD with symmetry matching, and k-mer enrichment
1.48.0  expansion batch: large-resource manifest and preflight, ColabFold and ESMFold structure prediction, pLDDT profiles and PAE summaries
1.48.1  patch: launch a script ColabFold runner through Python so Windows can execute the wrapper
1.49.0  expansion batch: RFdiffusion design, Vina docking and pose clustering, interface core/rim, signal peptide scan
1.50.0  expansion batch: interface-masked ProteinMPNN scoring, Prodigal gene prediction, HMMER domain annotation, VHH humanization scoring and PDBQT ligand preparation
1.50.1  patch: score the interface from conditional probabilities so per-residue NLL is available
1.50.2  patch: use a registered icon for vina_pose_cluster so Studio does not render the generic placeholder
1.51.0  expansion batch: Kabat numbering, paratope prediction, hotspot-masked design, batch docking and cavity druggability
1.52.0  expansion batch: IMGT numbering, glycosylation sites, LigandMPNN side-chain packing, biased design matrices and humanization mutations
1.52.1  patch: forward the per-residue bias matrix through --bias_by_res_jsonl
1.53.0  expansion batch: constrained amino-acid design, signal-peptide typing, pose RMSD, ligand strain and ridge probe
1.53.1  patch: version bump only; the design documents and test fixtures were published in 1.53.2
1.53.2  patch: publish the minibinder/VHH design route and competitive landscape
1.54.0  expansion batch: MLP embedding probe, B-factor disorder profile, transmembrane topology, liability scan and pairwise reaction enumeration
1.55.0  expansion batch: ligand interaction fingerprints, disorder propensity, interface cutoff scans and autoencoder novelty scores
1.55.1  patch: platform-layer competitive and economic assessment
1.56.0  expansion batch: DSSP segments, aggregation propensity, PCA reconstruction and net-charge profile
1.57.0  expansion batch: protonation sites, isoelectric point, beta propensity and isolation forest
1.58.0  expansion batch: interface temperature scan, kNN density, cysteine pairing and helical hydrophobic moment
1.53.0  next expansion batch
2.0.0  breaking change to plugin compatibility or operator IDs
```

## Version touch points

1. `pyproject.toml` — `[project] version`.
2. `biopipe/__init__.py` — `__version__`.
3. `docs/releases/vX.Y.Z.md` — release notes for the version.
4. Current counts and version text: `README.md`, `docs/UNIFIED_MAIN.md`,
   `docs/package_protocol.md`.
5. Reinstall the editable package after the bump so
   `importlib.metadata.version("biopipe-studio")` matches
   `biopipe.__version__`; a stale `*.egg-info` otherwise shadows the new value.

Generated indexes (`biopipe/builtin_packages.json`,
`docs/reference/operator_index.json`, `docs/reference/reader_index.json`,
`src/web/builtin_routes.json`) are outputs of `biopipe registry build` and
`scripts/build_operator_docs.py`. Never hand-edit them.

## Release procedure: expansion batch

1. Implement the new operators/Readers in the protocol v3 three-file form
   (`<module>.py`, `<module>.<Class>.parameters.json`,
   `<module>.<Class>.md`) and declare `provider` plus a literal `definition`.
2. Add focused tests: a hand-computable case and, where a trusted implementation
   exists (R, scikit-allel, scikit-learn, statsmodels, PLINK, …), a value-by-value
   comparison. Failure paths are part of the test set.
3. `python -m biopipe registry check` must report no errors, then
   `python -m biopipe registry build` regenerates the package and route indexes.
4. `python scripts/build_operator_docs.py` regenerates the adjacent Markdown and
   the documentation indexes; `--check` must be clean afterwards.
5. Increment MINOR, write `docs/releases/vX.Y.Z.md`, update the counts above.
6. Run the focused tests. Run the full suite only when the change touches shared
   core behavior, the registry discovery layer, or a release candidate is being
   prepared.
7. Commit, create the annotated tag `vX.Y.Z`, and push `main` and the tag. Never
   move or reuse a published tag.
8. Sync the Windows test copy and verify registry counts plus at least one
   existing workflow; user data directories are never overwritten.

## Patch procedure

Follow the same validation steps without adding capabilities, increment PATCH,
and state in the release notes that no operators or Readers were added. When a
fix accompanies an expansion batch that is not yet released, fold it into the
pending MINOR instead of publishing an interim PATCH.

## Compatibility

- Plugin dependency bounds are generated as `biopipe-studio>=X.Y.Z,<X+1`
  (`biopipe/developer.py`), so a MAJOR increment intentionally rejects plugins
  generated for the previous major line.
- Saved workflows keep their own frozen parameter values and implementation
  pins; a backend version bump alone does not re-pin them.
- Operator and Reader IDs are stable. Removing or renaming an ID is a breaking
  change and must be called out in the release notes.

Historical `v0.x` tags remain as published by the earlier library line; they are
history, not an alternative backend versioning scheme.
