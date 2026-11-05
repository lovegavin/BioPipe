# GenBank Reader

## Purpose

`GenBankReader` reads `.gb`, `.gbk` and `.gbff` files into a numeric summary Form:
one row per LOCUS record, with sequence length, GC fraction and feature count.
With `retain_records: true` (default), it also preserves original annotated
records as `info.genbank_records`, explicitly aligned with the record axis.

## Inputs and outputs

Supply two dimensions (normally `record`, `field`) and the standard label
configuration. The output is a full-mode Form. Sequence, compound/fuzzy feature
locations, qualifiers and circular/linear topology stay in the retained record
text. Subsetting the record axis keeps this metadata aligned.

## Parameters

The adjacent JSON is authoritative. `retain_records: false` omits original text
for summary-only analysis. `encoders` retains the standard table-reader behavior.
Saved workflows own their values independently of future defaults.

## Export example

Read an annotated plasmid, optionally select records, then connect `export_results`
with `format: genbank`. The resulting `.gbk` can be imported into SnapGene, ApE or
UGENE. Summary-only Forms cannot reconstruct sequences/features. Numeric summary
edits do not change original records; use a sequence-aware operation to edit them.

## Memory and validation

The parser iterates lines, but the summary and retained record text remain under
the existing full-mode planner/spill policy. It does not claim streaming output.
Original GenBank files can instead be carried as FileArtifacts. Export validates
retained records with Biopython. Tests use synthetic circular plasmids with joined
reverse-strand CDS features and verify a read/subset/export round trip; they do
not establish biological annotation quality.
