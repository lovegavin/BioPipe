# Operon Operator Library 2026.11.5.1

This is an independent operator-library update. The application remains v2.3.0;
no new EXE, application installation or protocol migration is required. The
library targets released Operon 2.0.4 and newer compatible applications.

## Unified branch export

- New `export_results` operator accepts Forms and FileArtifacts. Export any
  intermediate node on a branch while further calculations use the same data.
- Choose auto, native, CSV, TSV, NPY, FASTA, PDB or mmCIF through the independent
  parameter JSON. Native mode also handles other formats already represented by
  FileArtifacts. PDB/mmCIF requires original files rather than inventing structure
  annotations from tensors.
- Reuse same-task native paths without copying; copy external references into
  job-owned output for the existing file viewer and API. Row-wise tables and
  buffered NPY serialization avoid an additional whole-array conversion.
- ProteinMPNN retains original FASTA and score CSV; RFdiffusion retains original
  PDBs. Numeric Forms remain available. ProteinMPNN sequence/header axis metadata
  now follows design subsetting and reordering.

## Installation

Import the **Windows** `.operon-library.zip` in a Windows Operon operator library,
or the **Linux** bundle on a Linux installation. Existing independent library
installation/refresh paths apply; do not unzip files into the application package.
The seed wheel is for factory/library deployment, not a replacement desktop app.

See the adjacent `export_results` Markdown for format semantics and limitations.
Form-to-native attribution is within one task; carry FileArtifacts when crossing
task boundaries. Full-mode admission and the existing memory manager remain in
effect; this operator does not advertise the report-only streaming protocol.

## Verification

The platform verification artifacts record installation on the released 2.0.4
application, unchanged application files, preserved frozen routes and disabled
providers, idempotent installation, and a streaming worker run. Tests also cover
managed-memory export branches, native file persistence/reuse, converted formats
and existing result-file viewing. Protein design adapters use synthetic outputs;
real model weights and biological design quality are outside this test scope.
