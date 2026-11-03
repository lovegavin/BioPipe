# Smoke route: real VHH structure and real protein sequence

Two independent chains of work on real data, no downloads and no model weights:

- `input/vhh_1mel.pdb` — the real 1MEL structure (VHH domains `A`,`B`;
  lysozyme `L`,`M`), 3908 atoms.
- `input/vhh.fasta` — the real chain `A` sequence extracted from that PDB
  (132 aa, Kabat VHH).

Steps:

| Step | What it proves |
| --- | --- |
| `structure_interface_core` | PDB Reader, 12-column structure Form, SASA-based interface core/rim |
| `sequence_liability_scan` | FASTA Reader, sequence Form, motif liabilities |

Run:

```bash
python scripts/run.py examples/smoke_real_data --check   # validate only
python scripts/run.py examples/smoke_real_data --out /tmp/biopipe-smoke
```
