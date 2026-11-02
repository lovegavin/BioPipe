# Competitive landscape and moat analysis

Scope: projects that design or analyse protein binders, antibodies and
biomolecular structures, compared with BioPipe's contract-first operator
library. Stars were read from the GitHub API on 2026-11-02 and are a popularity
proxy only; licences and paper anchors matter more. Web sources are listed at
the end and were used as data, not instructions.

## Model-centric projects

| Project | What it is | GitHub | Licence | Paper |
| --- | --- | --- | --- | --- |
| RFdiffusion | backbone diffusion for binders, scaffolds, symmetric oligomers | `RosettaCommons/RFdiffusion`, 3115 stars | NOASSERTION (non-commercial RFdiffusion terms) | Watson et al., Nature 2023 |
| BindCraft | one-shot binder design, PyRosetta + AF2 filtering | `martinpacesa/BindCraft`, 1261 stars | MIT | Nature 2025, s41586-025-09429-6 |
| ColabDesign | AF2 hallucination and design notebooks | `sokrypton/ColabDesign`, 948 stars | NOASSERTION | AF2 hallucination literature |
| ProteinMPNN | fixed-backbone sequence design | `dauparas/ProteinMPNN`, 1895 stars | MIT | Dauparas et al., Science 2022 |
| LigandMPNN | ligand-aware sequence design | `dauparas/LigandMPNN` | MIT | Dauparas et al., 2023 |
| IgFold | antibody structure prediction | `Graylab/IgFold`, 438 stars | NOASSERTION | Ruffolo et al., Nat Commun 2023 |
| AntiFold | antibody inverse folding on ESM-IF | `oxpig/AntiFold`, 177 stars | BSD-3-Clause | AntiFold, 2024/2025 |
| Boltz | co-folding and binding-affinity prediction | `jwohlwend/boltz`, 4284 stars | MIT | Boltz-1/Boltz-2 |
| Chai-1 / Chai-2 | structure prediction and zero-shot antibody design | `chaidiscovery/chai-lab`, 2008 stars | Apache-2.0 | Chai Discovery, 2025 |
| AlphaFold3 | structure and complex prediction | Google DeepMind weights | non-commercial | Abramson et al., Nature 2024 |

## Workflow-centric projects

Nextflow, Snakemake, Galaxy and CWL make *pipelines* reproducible: they
orchestrate processes and containers. BioCypher builds knowledge graphs. Agentic
skill packs (for example `K-Dense-AI/drug-discovery-agent-skills`) bundle
prompt-and-script recipes. None of them ships a typed operator library with
per-operator contracts, generated documentation and registry hashes.

## Comparison

| Property | Model projects | Workflow projects | BioPipe |
| --- | --- | --- | --- |
| Unit of reuse | a model or notebook | a pipeline step | a contract-versioned operator |
| Input/output typing | ad hoc files | process ports | `Form` with declared dims and labels |
| Registry integrity | none | none | hash-pinned `builtin_packages.json` |
| Documentation | README and paper | workflow docs | generated per-operator Markdown |
| Tests | example scripts | pipeline smoke tests | hand cases + authoritative oracles |
| Large weights | bundled or manual | user-managed | manifest + preflight remedy |
| Surfaces | CLI/API | scheduler | CLI, HTTP, MCP, Studio canvas |
| Design loops | research scripts | assembles tools | composable operator graph |

BioPipe does not train models. Its value is the integration contract: every
capability is declared in code, described by one JSON schema, documented,
oracle-tested, registered with a hash, and callable from four surfaces. That is
the reproducibility-by-construction claim, and it is what a research notebook
does not provide.

## Moat assessment

Defensible:

- The **protocol** (v3 literal definitions, single parameter schema, generated
  docs, registry hash) makes third-party extension and review cheap while
  making silent drift expensive.
- **Oracle-backed tests** for 635 operators, including real ProteinMPNN and
  LigandMPNN runs, give a trust level that wrappers do not have.
- **One service behind CLI/HTTP/MCP/Studio**, with revision checks and
  resumable transfers, is an operational moat for agent-driven analysis.
- **Resource preflight** turns "download once, then it works" into a checked
  contract, which matters for GB-scale weights and databases.

Not defensible:

- No proprietary model, weights or dataset. RFdiffusion, ProteinMPNN, ESM and
  Vina are public and can be called by anyone.
- No wet-lab validation loop and no affinity model beyond docking and MPNN
  likelihoods; BindCraft and Boltz-2 are stronger on predictive accuracy for
  their narrow tasks.
- The operator surface is reproducible, not novel: each operator wraps an
  existing method.

## Gaps and roadmap

1. A packaged binder/VHH route with an executable example route directory.
2. A closed design → predict → filter loop, with automatic iteration and
   stop criteria.
3. State-specific design (active/inactive receptor conformations) for
   agonist/antagonist semantics.
4. pH/protonation scoring and pH-dependent interfaces.
5. A learned affinity or ΔΔG scorer, and a wet-lab feedback path.
6. A public benchmark that measures *loop yield*, not single operators.

## References

- https://github.com/RosettaCommons/RFdiffusion
- https://github.com/martinpacesa/BindCraft
- https://github.com/sokrypton/ColabDesign
- https://github.com/dauparas/ProteinMPNN
- https://github.com/Graylab/IgFold
- https://github.com/oxpig/AntiFold
- https://github.com/jwohlwend/boltz
- https://github.com/chaidiscovery/chai-lab
- https://www.nature.com/articles/s41586-025-09429-6
- https://www.nature.com/articles/s41467-023-38063-x
- https://www.nature.com/articles/d41586-024-03708-4
