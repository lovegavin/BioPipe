# Unified main integration

This source update establishes one current application and authoring protocol on
`main`. Application version: **1.78.1**. SDK version: **3.1.0**. Operator protocol:
**v3**. The latest previously published desktop binaries are a separate artifact;
this integration does not claim to have rebuilt or accepted a new Windows EXE.
  release 1.38.0 adds side-chain chi angles, k-mer composition profiles, embedding PCA loadings, reaction SMARTS application and restriction-site scanning.
  release 1.39.0 adds per-residue surface hydrophobicity, six-frame ORF finding, Morgan atom-environment histograms, metal coordination shells and CDR length profiles.
  patch 1.39.1 fixes metal-shell indexing for ions that are not the first atom of the structure.
  release 1.40.0 adds backbone dihedral and Ramachandran classes, CA distance matrices, ring-system statistics, charge profiles and ligand burial.
  patch 1.40.1 resolves the PDB fixture path relative to the test module so the dihedral oracle runs on Windows.
  release 1.41.0 adds helix-pair geometry, ligand clash detection, Murcko scaffold fingerprints, embedding k-means silhouettes and CpG island scans.
  release 1.42.0 adds helix bend profiles, halogen bond scans, design clustering and a spectral embedding projection.
  release 1.43.0 adds buried cavity scans, ligand residue contact maps, scaffold trees and tandem repeat finding.
  release 1.44.0 adds masked ProteinMPNN design, secondary-structure bridge networks, functional-group counts and GC skew profiles.

## Source ancestry

- Application baseline: `8898d175bc8e7044cf881dee47ded5892ec9c74b` (Studio v0.8.3).
- Author's main snapshot: `9b6bbdd024fb4f59aa65b0850f72c36ec6df4538` (v0.115.0).
- Historical source: the `legacy-main-20261101` tag and its release ZIP preserve
  that complete main snapshot. It is not installed as a second runtime.

The integration preserves the desktop branch's existing 86 extensions, including
Hi-C file artifacts, streaming and disk readers, managed execution and unified
figure outputs. It adds 407 previously missing upstream extensions through an
explicit conversion to v3. The combined registry contains **667 operators and
101 Readers**, in seven independently manageable providers, and **24 route
templates**. Counts describe this integration, not hard limits in the software. Backend
**1.2.0** adds the Arrow reader, seasonal decomposition and Fst-family
statistics, **1.3.0** adds phylogeny-aware diversity operators and a PhyloXML
reader, and **1.4.0** adds causal-inference operators and a MuData reader, and
**1.7.0** adds Moran's I, indicator species, affine pairwise alignment and a PDBML reader; see [the v1.7.0 release notes](releases/v1.7.0.md).
**1.10.0** adds exact Poisson tests, binomial confidence intervals, chi-square goodness of fit and redundancy analysis; **1.11.0** adds weighted kappa, the turning point test, the raw periodogram and species-pool richness estimators; **1.12.0** adds the Lilliefors and Pearson normality tests, the Cox-Stuart trend test and the Mann-Kendall rank test; see [the v1.12.0 release notes](releases/v1.12.0.md); **1.13.0** adds the Mood two-sample scale test, the two-sample F test and the D'Agostino skewness and Anscombe-Glynn kurtosis tests; see [the v1.13.0 release notes](releases/v1.13.0.md); **1.14.0** adds linear discriminant analysis, simple correspondence analysis, nestedness (NODF) and Rényi diversity profiles; see [the v1.14.0 release notes](releases/v1.14.0.md). **1.15.0** adds 24 beta-diversity indices, Tsallis diversity, variation partitioning and a CCP4/MRC volume reader; see [the v1.15.0 release notes](releases/v1.15.0.md). **1.16.0** adds bio-environment matching, the Morisita index and NIfTI/NRRD volume readers; see [the v1.16.0 release notes](releases/v1.16.0.md). **1.17.0** adds Nelson-Aalen cumulative hazard, Gower distance, PAM clustering and STL/OBJ mesh readers; see [the v1.17.0 release notes](releases/v1.17.0.md). **1.18.0** adds OPTICS, BIRCH and HDBSCAN clustering plus PLY and OFF mesh readers; see [the v1.18.0 release notes](releases/v1.18.0.md). **1.19.0** adds ProteinMPNN sequence design, ESM masked marginals, minibinder interfaces, ligand contact profiles, a protein-aware FASTA alphabet and full-atom PDB columns; see [the v1.19.0 release notes](releases/v1.19.0.md). **1.19.1** fixes ProteinMPNN invocation on Windows by passing POSIX-style paths; see [the v1.19.1 release notes](releases/v1.19.1.md). **1.20.0** adds RDKit molecular descriptors, Morgan fingerprints and SMILES standardization, ESM sequence embeddings and interface buried-area analysis; see [the v1.20.0 release notes](releases/v1.20.0.md). **1.20.1** makes the ProteinMPNN path assertions platform-neutral so the focused suite passes on Windows; see [the v1.20.1 release notes](releases/v1.20.1.md). **1.21.0** adds ProteinMPNN score-only scoring, antibody developability metrics, ESM masked-marginal pseudo-likelihoods, RDKit Murcko scaffolds and a PDBQT reader; see [the v1.21.0 release notes](releases/v1.21.0.md). **1.22.0** adds zero-shot ESM variant-effect scans, interface-focused ProteinMPNN design, RDKit ADMET rule sets, RDKit conformer energies and Kabat-style antibody CDR annotation; see [the v1.22.0 release notes](releases/v1.22.0.md). **1.23.0** adds Kabsch structure RMSD, interface hotspot profiles, RDKit similarity matrices, PAINS filter alerts and ligand efficiency metrics; see [the v1.23.0 release notes](releases/v1.23.0.md). **1.24.0** adds contact networks and backbone hydrogen bonds, maximum common substructures, and LigandMPNN ligand-aware sequence design and scoring; see [the v1.24.0 release notes](releases/v1.24.0.md). **1.24.1** fixes the declared output metadata of the new operators so the runner contract check accepts their forms and adds runner-level regression tests; see [the v1.24.1 release notes](releases/v1.24.1.md). **1.25.0** adds ESM-IF inverse-folding design and scoring, binder-by-target contact maps, Kabat CDR physicochemical profiles and RDKit tautomer canonicalization; see [the v1.25.0 release notes](releases/v1.25.0.md). **1.26.0** adds ESM-IF mutation scans, ESOL solubility estimates, SMARTS match matrices, interface hydrophobic patches and CDR hydrophobicity profiles; see [the v1.26.0 release notes](releases/v1.26.0.md). **1.27.0** adds oral-bioavailability rule sets, QED drug-likeness, per-residue SASA and CDR liability motif scanning; see [the v1.27.0 release notes](releases/v1.27.0.md). **1.28.0** adds ESM-IF partial redesign, Ertl synthetic accessibility scoring, per-residue B-factor profiles and sequence complexity metrics; see [the v1.28.0 release notes](releases/v1.28.0.md). **1.29.0** adds interface atom-pair distance histograms, residue packing density, sliding-window hydrophobicity profiles, BRICS/RECAP fragment profiles and ProteinMPNN conditional-probability profiles; see [the v1.29.0 release notes](releases/v1.29.0.md). **1.30.0** adds ProteinMPNN multi-model ensemble scoring, maximum-common-substructure clustering, interface hydrogen-bond networks and PROSITE-style motif scanning; see [the v1.30.0 release notes](releases/v1.30.0.md). **1.31.0** adds ProteinMPNN design-position entropies, ESM embedding PCA and nearest neighbours, disulfide bonds and salt bridges; see [the v1.31.0 release notes](releases/v1.31.0.md). **1.31.1** defaults the ProteinMPNN designer interpreter to the running interpreter so the position-entropy operator starts on Windows, where `python3` resolves to the store alias; see [the v1.31.1 release notes](releases/v1.31.1.md). **1.32.0** adds ProteinMPNN design-position amino-acid profiles, amide-pi and cation-pi contacts, aromatic stacking classification and RDKit conformer clustering; see [the v1.32.0 release notes](releases/v1.32.0.md). **1.33.0** adds ESM-IF per-position entropy, ligand-aware active-site redesign, ProteinMPNN amino-acid bias scans and seeded random SMILES augmentation; see [the v1.33.0 release notes](releases/v1.33.0.md). **1.34.0** adds CDR-fixed antibody framework redesign, multi-checkpoint ProteinMPNN consensus, binder-interface ESM-IF redesign and ProteinMPNN temperature ladders; see [the v1.34.0 release notes](releases/v1.34.0.md). **1.35.0** adds ProteinMPNN interface redesign, sliding-window ESM-IF masked redesign, per-position native recovery and RDKit pharmacophore feature counts; see [the v1.35.0 release notes](releases/v1.35.0.md). **1.35.1** fixes the RDKit pharmacophore feature-file lookup on Windows profiles whose path contains non-ASCII characters; see [the v1.35.1 release notes](releases/v1.35.1.md). **1.35.2** aligns the pharmacophore test oracle with the ASCII-safe feature file and normalises multi-chain ProteinMPNN FASTA records in the native-recovery scan; see [the v1.35.2 release notes](releases/v1.35.2.md). **1.36.0** adds dihedral-based secondary-structure segments, absolute and relative contact order, BRICS fragment overlap matrices, and ProteinMPNN design-diversity clustering; see [the v1.36.0 release notes](releases/v1.36.0.md). **1.36.1** falls back to the repository `vanilla_model_weights` directory when no weights path is supplied, so the design-diversity operator runs on Windows; see [the v1.36.1 release notes](releases/v1.36.1.md).

Coordinate precision fixes from upstream are applied to the existing CSV,
Parquet, BED, GFF3 and GTF implementations. Numeric columns retain float64 when
float32 would change their values. Shared machine-learning helpers no longer
construct parameter schemas during import; each concrete model owns its JSON.
Algorithms are not implicitly advertised as streaming or CUDA capable.

## Application boundary

`biopipe/application.py` composes workflow, task and artifact services over the
existing worker, SSH coordinator, memory admission and spill implementation.
`biopipe/control_api.py` exposes these through `/api/v1` in both Studio and a
loopback headless host. `biopipe/headless.py` owns discovery, startup and shutdown
without a canvas or frontend build.

- **API:** structured software integration, workflow revisions, durable task
  identifiers, bounded logs, artifact metadata and original output files.
- **CLI:** scripts, servers, reproducible commands and library maintenance. A
  detached service can continue after the submitting command exits.
- **MCP:** agent-oriented tools, selective operator documentation retrieval and
  optional live-canvas collaboration. Read/edit/run permissions remain separate.

No independent scheduler or scientific execution engine was introduced. Saved
workflows retain their own parameter and execution JSON. Submitted jobs freeze
their parameters and implementation pins. Request IDs protect retries from
accidentally submitting a second job; revision checks protect saved edits.

See [the API/CLI/MCP contract](headless_api.md) for commands, permissions,
error responses, service lifecycle and the limits of interrupted-job recovery.

## Authoring and discovery

Every bundled extension has code, an independent parameter schema JSON and an
adjacent Markdown document. [Protocol v3](operator_protocol.md) and the
[SDK guide](sdk_quickstart.md) are the canonical authoring instructions. New templates include
documentation; existing packages without a document still expose their schema.

Search returns compact indexed summaries. Detailed retrieval reads only selected
IDs and sections, optionally from a job's pinned library generation. Startup and
search use compiled metadata without importing operator modules or scanning their
source trees. Explicit registry maintenance validates and rebuilds that metadata.

Generated reference pages are marked as generated. They provide source-derived
usage, contracts and parameter references, not independent scientific review.
Authored guides and executable examples supplement them. Documentation-only and
nonbreaking default changes do not become new executable identities; workflow
values stay frozen. Wheel integrity still covers the complete archive.

## Frontend selection

The existing Studio layout, tab handling, selection/undo, remote controls, memory
settings and result views are retained. Adopted changes include canonical library
categories, searchable usable Reader cards, concise descriptions and execution-
target-aware platform hints. An explicit Reader selection survives save/export,
pinning, upload, SSH preparation and actual reading.

See [frontend integration decisions](FRONTEND_MERGE.md). Existing `TxtReader`
delegation parameters are distinct from the new optional `source.reader` ID.

The legacy incremental-test script and its duplicate reference-page gates are
not another maintenance path: the current static registry, documentation check
and focused pytest suites cover those responsibilities. Existing explicitly open
parameter maps remain compatible; new SDK templates use closed top-level schemas.
Publication heatmaps retain physical output dimensions instead of adopting a
new hardcoded matrix-cell limit. Resource admission remains the execution guard.

## Validation scope

The integration is checked with protocol, pin/default/documentation lifecycle,
managed-memory, disk/compression, CLI/MCP process, HTTP permission, SSH fixture,
frontend and public-data route tests. Optional dependency and real Linux-tool
tests report skips explicitly; local synthetic SSH fixtures are not a new
live-cloud acceptance run. See the [acceptance record](validation/UNIFIED_MAIN_0_116.md)
for concrete results and limits, rather than inferring coverage from the extension
count.

Five curated upstream public-data examples are retained in
`examples/route_combinations/`. Their own frozen parameter files and validation
notes distinguish executable regression checks from the author's biological
interpretations. Bundled template validation does not mean every possible
parameter combination or third-party tool has been scientifically validated.
