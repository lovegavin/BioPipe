# Extension policy: what belongs in the core library

Operon ships a large operator library so agents can call a **validated**
analysis instead of writing code. That only works if the library is curated.
This page records the curation rule, so users and agents can decide together
what to add and what not to add.

## What qualifies for the core library

An operator or Reader belongs in core when it is **hard to implement correctly
or hard to verify**, and **analytically important**:

1. **Model wrappers** around published, widely used bioinformatics or ML models
   (ProteinMPNN, LigandMPNN, ESM/ESM-IF, AntiFold, Boltz, AlphaFold-style
   predictors, RFdiffusion, docking engines, HMMER/Pfam, Prodigal, DSSP).
   Rationale: the wrapper must reproduce the official invocation, parse its
   formats, handle weights and failures, and stay correct across versions.
2. **Algorithms with non-obvious correctness**: Kabat-Sander hydrogen-bond
   energies, SASA, symmetry-aware ligand RMSD, interface core/rim, secondary
   structure, spectral domain boundaries, PPIs and label alignment.
3. **Contract-heavy integrations**: anything where getting the `Form` dims,
   labels, encodings or memory mode wrong silently corrupts downstream results.
4. **Oracles that need an independent implementation**: if the only way to know
   the answer is to compare with an authoritative tool, the wrapper is valuable.

## What does not belong in core

- Trivial arithmetic on a sequence or a table that an agent can write in a few
  lines with the same certainty (single-formula scores, column reshuffles,
  format conversions with no semantics).
- Niche or cold formats and one-off laboratory conventions. A Reader for these
  should be generated on demand for the user's specific data.
- Anything that cannot be verified: no hand case, no authoritative oracle, no
  fake-runner contract test. If it cannot be tested, it is documented instead.
- Duplicates of an existing operator with a different name or a narrower filter.

Rule of thumb: **if a competent agent could write it correctly in one
sitting, it is documentation or a user extension, not a core operator.**

## Requesting an on-demand extension

A user can ask the agent to add an operator or Reader for their data or model at
any time. A good request names:

1. the input (file type, exact columns, a small anonymized sample),
2. the expected output (table columns, axes, labels, value ranges),
3. an authoritative implementation or reference to compare against
   (official repository, paper with equations, or a small known-answer case),
4. the environment (installed package versions, weight locations, GPU/CPU).

The agent then authors the three-file operator form (implementation, parameter
JSON, generated Markdown), an oracle-backed test, rebuilds the registry and
documents the capability. The extension follows the same rules as core: typed
contracts, declared parameters, no hidden file assumptions, and a resource
manifest entry when GB-scale weights are involved.

Extensions that turn out to be generally useful can be promoted into a batch:
they are then covered by the release notes, the registry hash and the Windows
verification run.

## What "done" means for a hard capability

- The official code path is reproduced (same flags, same weights layout).
- Failure modes are explicit: missing binary, missing weights, timeout,
  malformed output, empty result.
- A test either runs the real model on a tiny input or exercises the exact
  invocation and parsing contract with a fake runner, and the release note says
  which of the two was used.
- The capability is listed in `docs/large_resources.md` and
  `src/task/step/steps/resources.json` when it needs downloadable assets.
