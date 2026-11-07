# Operon Operator Library 2026.11.5.2

An independent library update for released Operon 2.0.4 and newer compatible
applications. Updating these operators does not require a new EXE. The optional
specialist-viewer UI is provided separately by Studio v2.4.0.

- Extend the existing `export_results` operator with HIC/Cooler, annotated GenBank,
  BED/bedGraph, GraphML and Newick. Select formats through independent parameter
  JSON; retain native-file reuse and branch export while downstream work continues.
- HIC/Cooler export validates raw contact counts, chromosome sizes, bin coordinates
  and resolution, and writes bounded batches. Balanced/log/OE values cannot be
  reverse-converted to raw counts. `hictkpy` is declared as an export dependency.
- GenBank Reader can retain original records for annotation-preserving export;
  record retention is full-mode metadata, not a streaming promise. Sequence-only
  exports do not invent annotations.
- Genome-track, network and tree exports validate their domain metadata. Generic
  tensors are not advertised as convertible to arbitrary native formats.
- Preserve protocol v3, frozen workflow parameters, memory planning and disk/stream
  interfaces. Existing provider installations and disabled states remain intact.

Choose the Windows or Linux native library bundle for that host and import it in
Library Management. The seed wheel is for new deployments. See the adjacent
operator Markdown and the platform verification assets for exact requirements.
