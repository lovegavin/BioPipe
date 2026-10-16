# Upstream Changelog

Version history of the BioPipe Python engine and its operators.

| Version | Date | Summary |
|---|---|---|
| v1 | initial | Four-protocol engine, 12 Readers, 18 Steps, GWAS demo |
| v2 | current | 28 new Steps, 1 new Reader, 1 Reader change, five end-to-end paths |
| v3 | current | GO enrichment pipeline, 2 new Readers, 7 new Steps, reader-owns-format principle |
| v4 | current | Sequence / annotation QC / interval analysis; 11 new Steps, 1 Reader contract extension, 7 readers patched for CRLF and blank-line handling, 4 new pipelines |
| v5 | current | Single-cell RNA-seq pipeline, E. coli GC-skew pipeline, peak-to-gene association; 4 new Steps, 1 Step rewritten, 1 Step contract generalised, 3 new pipelines, 116-check verification suite |

Each entry lists the new Readers, new Steps, contract changes, and end-to-end pipelines added in that version. Breaking changes are marked explicitly.

The engine version is independent of the downstream Studio version. Downstream release notes live in `docs/releases/`.