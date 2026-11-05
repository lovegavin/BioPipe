# Application and library versioning

Application, operator library and SDK are independent release axes. **Adding an
operator or Reader does not require a software release.** The former rule that
incremented backend MINOR for every expansion batch is retired. Historical
numbers below remain unchanged; they do not prescribe future software versions.

| Axis | Source of truth | Published tag | When it changes |
| --- | --- | --- | --- |
| Application | `pyproject.toml`, `biopipe/__init__.py` | `vX.Y.Z` | Engine, service, frontend/host integration or application fixes |
| Operator library | `library/release.json` | `library-vYYYY.M.D[.N]` | Operators, Readers, guides, defaults, helpers or resource declarations |
| Provider/operator | v3 provider and literal declaration | Inside the library/wheel | Executable or contract version changes |
| Protocol/SDK | protocol schemas and SDK | Explicit SDK release | Authoring/runtime contract changes |

The existing 2.1/2.2 source labels came from the former expansion policy. They
are not a requirement to update a user's already installed Studio application.
Do not retroactively rename published versions or tags.

## Application rules

- MAJOR: breaking engine/API/runtime compatibility.
- MINOR: backward-compatible application capabilities.
- PATCH: application fixes.
- Operator-only changes use the library release process, including operator bug
  fixes. Application version files and desktop archives stay unchanged.
- A library that needs new runtime features declares a tested minimum application
  version. Publish that application separately before depending on it.

## Coordinated 3.0.0 release

BioPipe 3.0.0 and BioPipe Operator Library v3.0.0 are released together. Both
products use version `3.0.0`, published as annotated tags `v3.0.0` and
`library-v3.0.0`. The library declares `minimum_application` and
`build_application` `2.4.1` (the oldest supported application) while its own
version is `3.0.0`. This is a coordinated milestone, not a new
versioning rule: later operator-only changes continue to use the library
release process.

## Library rules

Follow [independent library releases](library_releases.md). Use protocol-v3 code,
adjacent parameter JSON and Markdown, update the static indexes, and test against
the minimum released application in an isolated environment. `build_application`
and `minimum_application` must match in the release configuration. CI rejects a
tag/version mismatch, installs the frozen application wheel, and never imports
an editable checkout as the engine during library verification.

Publish under a new `library-v…` tag after Windows and Linux checks pass. The
workflow publishes only the library ZIP, checksum and verification report and
sets `make_latest=false`, preserving the latest application release. Never move
or reuse a published tag. Saved route templates use their own save/import path;
a library bundle does not silently replace saved routes.

## Compatibility

- Keep operator/Reader IDs stable. Breaking contract changes require an explicit
  operator/provider version change and migration guidance; they do not by
  themselves require a new engine.
- Frozen workflow parameter JSON and implementation pins are not rewritten by
  library installation. Old jobs retain their snapshots.
- Additional Python dependencies use the existing shared/conflict-isolated
  dependency manager. Large resource metadata travels inside the provider;
  external binaries, weights and databases retain explicit requirements.
- Generated indexes are outputs of `biopipe registry build` and
  `scripts/build_operator_docs.py`; do not hand-edit them.

## Historical application labels under the former expansion policy

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
1.58.1  patch: extension policy for hard capabilities and on-demand extension
1.59.0  hard batch: Boltz-2 co-folding prediction and Foldseek structural search wrappers
1.59.1  patch: launch script wrappers through the interpreter on Windows
1.59.2  patch: resolve script wrappers by path and exercise the interpreter guard in tests
1.59.3  patch: Foldseek real-run verification, drop the unsupported --max-hits flag
1.59.4  patch: align Boltz with its real CLI and document blocked hard capabilities
1.60.0  batch: real Boltz-1 inference with an empty MSA and a weight cache, plus Foldseek real-search evidence
1.61.0  batch: Boltz-2 protein-ligand inference with affinity verification and YAML version/affinity-binder fixes
1.62.0  batch: real ESMFold inference through transformers weights_dir, with checksum-verified 3B weights
1.63.0  batch: AntiFold inverse-folding scoring with verified 540 MB weights and a real 1MEL run
1.63.1  patch: platform-neutral fixture path in the AntiFold validation test
1.64.0  batch: ColabFold single-sequence inference against real AlphaFold-2 parameters, device flag removed
1.65.0  batch: real Pfam/HMMER domain scan against a pressed Pfam-A 38 and an env-neutral test
1.66.0  batch: OpenMM potential-energy and minimization operator verified on a VHH
1.67.0  batch: MM/GBSA binding-energy estimate with bonded/nonbonded/GB term decomposition
1.68.0  batch: computational alanine scanning of interface residues with MM/GBSA delta-delta-G
1.69.0  batch: PROPKA protonation states and per-residue charges through pdb2pqr
1.70.0  batch: short implicit-solvent molecular dynamics with drift statistics through OpenMM
1.71.0  batch: AntiFold antibody inverse-folding designs and per-residue log-probability profiles
1.72.0  batch: Boltz-2 binding-affinity predictions and summary tables
1.73.0  batch: OpenFold structure prediction with single-sequence alignments
1.74.0  batch: ligand geometry and protein-clash quality checks
1.75.0  batch: TM-score structural similarity with iterative C-alpha superposition
1.75.1  patch: real ESMFold-3B verification, fair-esm Python 3.12 and checkpoint-key fixes documented
1.76.0  batch: CAPRI DockQ scoring with native contacts, interface and ligand RMSD
1.77.0  batch: per-residue lDDT with the 15 A inclusion radius and four thresholds
1.78.0  batch: short OpenMM implicit-solvent MD with per-residue C-alpha RMSF
1.78.1  patch: skip the MD integration tests when OpenMM or PDBFixer is absent
1.79.0  batch: PoseBusters protein-ligand pose validation
1.80.0  batch: fpocket pocket detection built from source
1.81.0  batch: RNA secondary structure folding through ViennaRNA RNAfold
1.82.0  batch: RNA partition-function ensemble statistics
1.83.0  batch: AutoDock Vina docking through the official Python engine
1.84.0  batch: flexible-ligand PDBQT torsion trees
1.85.0  batch: flexible-receptor docking with BEGIN_RES side chains
1.86.0  batch: MD secondary-structure occupancy from DSSP frames
1.87.0  batch: RNA-RNA duplex hybridization through ViennaRNA RNAduplex
1.88.0  batch: RNA dimer cofolding and equilibrium concentrations through RNAcofold
1.89.0  batch: MD residue contact occupancy from heavy-atom distances
1.90.0  batch: MD salt-bridge occupancy between acidic and basic side chains
1.91.0  batch: MD hydrogen-bond occupancy from donor-H...acceptor geometry
1.92.0  batch: MD per-residue solvent-accessible surface statistics
1.93.0  batch: MD backbone phi/psi Ramachandran occupancy
1.94.0  batch: redock pose validation through PoseBusters
1.95.0  batch: ligand displacement after receptor superposition along MD frames
1.95.1  patch: real Prodigal verification on the phage lambda genome
1.95.2  patch: real HMMER domain-scan verification against Pfam-A
1.96.0  batch: per-residue ESM-3 embeddings from the official open model
1.96.1  patch: keep ESM-3 contract tests runnable without the esm package installed
1.97.0  batch: ESM-3 structure-conditioned inverse folding
1.98.0  batch: ESM-3 sequence-to-structure prediction with pLDDT and pTM
1.98.1  patch: make the ESM-3 contract tests run without the esm package
1.98.2  patch: install the esm stub in the ESM-3 fold round-trip test
1.99.0  batch: Gaussian and anisotropic network models for flexibility analysis
1.100.0  batch: essential-dynamics PCA and quasiharmonic entropy from trajectories
1.101.0  batch: free-energy landscapes and conformational clustering from trajectories
1.102.0  batch: dynamic cross-correlation and allosteric communication paths
1.103.0  batch: hydrogen-bond residence times from trajectories
1.104.0  batch: RNA ensemble accessibility via the ViennaRNA Python bindings
1.105.0  batch: per-residue interface energy decomposition in vacuum
1.106.0  batch: Markov state models from trajectory clustering
1.107.0  batch: time-lagged independent component analysis
1.108.0  batch: two-strand RNA cofold ensemble statistics
1.109.0  batch: chi1 rotamer populations and transitions from trajectories
1.110.0  batch: DSSP secondary-structure state transitions from trajectories
1.111.0  batch: ESM-3 secondary-structure track prediction
1.111.1  patch: install an esm stub so the ESM-3 secondary-structure test runs without the package
1.112.0  batch: ESM-3 solvent-accessibility track prediction
1.113.0  batch: Boltz complex prediction with interface confidence
1.113.1  patch: launch script Boltz runners through Python so Windows can run the test double
1.113.2  patch: write the Boltz test double with UTF-8 so non-ASCII Windows temp paths work
1.114.0  batch: Foldseek pairwise structural alignment
1.115.0  batch: resource provisioning engine and agent environment-repair guide
1.116.0  batch: Foldseek structural clustering
1.116.1  patch: mirror-first wheel installs with a conda C++ toolchain and a source-build retry
1.116.2  patch: repair existing managed environments that lack the C++ toolchain
1.117.0  batch: MD interface contact occupancy
1.117.1  patch: install pdbfixer from conda and keep build-fragile sdists off the pip solve
1.117.2  patch: ship a bundled pdbfixer wheel and prepare compilers only for source builds
1.117.3  patch: keep pdbfixer and openmm out of the default pip solve (optional conda extra)
1.117.4  patch: report missing OpenMM extras instead of failing the install
1.117.5  patch: install pysam from bioconda and retry sdists before adding compilers
1.117.6  patch: add pysam after the pip solve so conda NumPy cannot block it
1.117.7  docs: remote-install quick checklist and agent working notes (no execution change)
1.117.8  patch: keep antifold in a dedicated environment (numpy 1.26 pin conflicts with pydeseq2)
1.117.9  docs: end-to-end quick start (desktop, MCP, agent, remote server, canvas, runs)
1.117.10  patch: launch the managed installer directly instead of through micromamba run
1.117.11  docs: record the 8-12 GB download budget and cache reuse for managed installs
1.117.12  docs: DeepSeek Harness first for MCP, plus the clean-environment acceptance checklist
1.117.13  patch: install pdb2pqr and ViennaRNA after pip and treat boltz/foldseek as optional binaries
1.118.0  batch: ESM-3 masked-prompt sequence generation (709 operators)
1.118.1  patch: resolve routes from the managed code dir when BioPipe is installed into site-packages
1.118.2  patch: pair env-<digest> with code-<digest> for route discovery, grant MCP run permission by default, and document every remote-connection field
1.118.3  patch: register BatteryFull, File and CirclesThree so no operator or reader falls back to the placeholder icon
1.118.4  docs: specify the DeepSeek Harness workspace, permission level and a minimal example prompt
1.118.5  docs: ship an offline real-data smoke route (1MEL structure, VHH sequence) with recorded results
1.118.6  patch: track the smoke-route inputs (git force-add past the input/ ignore rule)
1.118.7  docs: step-by-step quickstart with a runnable MCP prompt for the real-data smoke route
1.118.8  patch: pass micromamba package specs as separate arguments so managed installs can create the environment
2.1.0    batch: genome annotation I - antiSMASH, Rfam, tRNAscan-SE and AMRFinderPlus (713 operators)
2.1.1    patch: import Biopython lazily in the antiSMASH real test (no capability change)
2.2.0    batch: genome assembly I - Flye, QUAST and minced CRISPR (716 operators)
3.0.0  coordinated application + library release: native file export registration, sequence FASTA export
1.118.9  docs: quickstart asks the agent to design, adjust, validate and submit the real-data route instead of reusing a fixed one
1.119.0  feature: agent canvas writes into the user's tab with execution switching, water-safe structure defaults, richer interface/liability exports and MCP session recovery
1.53.0  next expansion batch
2.0.0  breaking change to plugin compatibility or operator IDs
```
