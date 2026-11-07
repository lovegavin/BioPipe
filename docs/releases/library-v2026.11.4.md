# Operon Operator Library 2026.11.4

This is an **operator library update**, not a Studio application release. Install
the `.operon-library.zip` through **Library manager → Import package**, or:

```bash
operon plugin install ./Operon-Library-v2026.11.4-Windows.operon-library.zip
```

Requires **Operon Studio 2.0.4 or newer** and protocol v3. Existing Lite and Full
2.0.4 packages can install it without replacing the EXE. Studio downloads remain
on the [v2.0.4 software page](https://github.com/lovegavin/Operon/releases/tag/v2.0.4).

Choose **Windows** for the Windows desktop and **Linux** for a Linux server.
The v2.0.4 installer rebuilds and compares native wheel archives, whose metadata
differs across systems; the two envelopes contain the same library sources.

The library contains **716 operators and 101 Readers**, including seven additions
relative to the Studio 2.0.4 seed:

- `amrfinder_plus`: antimicrobial resistance annotation with AMRFinderPlus.
- `antismash_bgc`: biosynthetic gene cluster annotation with antiSMASH.
- `rfam_scan`: covariance-model RNA family search with Infernal/Rfam.
- `trnascan_se`: tRNA detection with tRNAscan-SE.
- `flye_assemble`: long-read assembly with Flye.
- `assembly_stats`: assembly evaluation with QUAST.
- `crispr_array_detect`: CRISPR array detection with minced.

The library owns and distributes its resource manifest, parameter JSON and
Markdown guides. Database paths are configurable and no longer default to an
author's machine. The application, frontend, saved parameter values, memory
planner and streaming interfaces are not replaced by this update.

Six existing adapters now import optional PyTorch/Biopython/RDKit dependencies only
when executing, so they do not prevent unrelated operators from registering.
The older embedding autoencoder still requires a preinstalled PyTorch runtime;
automatic installation of new PyTorch packages under 2.0.4 can fail on bundled
Python-3.12-only test sources. This library does not alter the application compiler
or claim to fix that separate runtime limitation.

Validation covers independent installation on the released 2.0.4 engine,
resource resolution, historical pins, frozen parameters, repeat imports,
disabled providers, a real streaming worker, and synthetic external-tool
adapter/parser/error cases. It does **not** claim end-to-end scientific validation
of the seven external programs or ship their databases. Their declared platform,
binary and resource requirements still apply.

See [independent library releases](https://github.com/lovegavin/Operon/blob/library-v2026.11.4/docs/library_releases.md)
for the update and publication workflow. The version namespace `library-v…` is
independent of software `v…`; a new library never displaces GitHub's latest
software release.
