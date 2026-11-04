# BioPipe Operator Library 2026.11.4

This is an **operator library update**, not a Studio application release. Install
the `.biopipe-library.zip` through **Library manager → Import package**, or:

```bash
biopipe plugin install ./BioPipe-Library-v2026.11.4.biopipe-library.zip
```

Requires **BioPipe Studio 2.0.4 or newer** and protocol v3. Existing Lite and Full
2.0.4 packages can install it without replacing the EXE. Studio downloads remain
on the [v2.0.4 software page](https://github.com/lovegavin/BioPipe/releases/tag/v2.0.4).

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

Two existing adapters now import optional PyTorch/Biopython dependencies only
when executing. The embedding autoencoder also declares its PyTorch dependency
explicitly so the dependency manager can prepare it instead of failing at import.

Validation covers independent installation on the released 2.0.4 engine,
resource resolution, historical pins, frozen parameters, repeat imports,
disabled providers, a real streaming worker, and synthetic external-tool
adapter/parser/error cases. It does **not** claim end-to-end scientific validation
of the seven external programs or ship their databases. Their declared platform,
binary and resource requirements still apply.

See [independent library releases](https://github.com/lovegavin/BioPipe/blob/library-v2026.11.4/docs/library_releases.md)
for the update and publication workflow. The version namespace `library-v…` is
independent of software `v…`; a new library never displaces GitHub's latest
software release.
