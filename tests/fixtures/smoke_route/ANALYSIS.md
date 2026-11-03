# Smoke route results (real 1MEL data)

Recorded from `python scripts/run.py <copy-of-this-directory>` on the reference
machine (CPU, no model weights).

## Input

| Item | Value |
| --- | --- |
| Structure | 1MEL (RCSB), 3908 atoms, chains `A`,`B` (VHH), `L`,`M` (lysozyme) |
| Sequence | chain `A` Cα sequence, 132 aa, `VQLQASGGGSVQAGGSLRLS...` |

## Output

| Step | Result |
| --- | --- |
| `structure_interface_core` (binder `A,B` vs target `L,M`, 4.5 Å, 92 probe points) | 99 interface residues, 58 core, 41 rim |
| `sequence_liability_scan` | 10 liabilities: 5 oxidation, 3 isomerization, 2 deamidation |

Wall time: 2.7 s total (2.7 s for SASA, <0.01 s for liabilities).

## What it validates

- `PdbReader` 12-column structure Form (`bfactor` included) and chain selection.
- Shrake–Rupley SASA implementation on a real antibody–antigen complex.
- `FastaReader` protein alphabet and motif scanning on a real VHH sequence.
- Route parameter files, registry hashes and the runner end to end, offline.

## Commands

```bash
python scripts/run.py examples/smoke_real_data --check        # validate only
cp -r examples/smoke_real_data /tmp/smoke && python scripts/run.py /tmp/smoke
```

The second command writes `output/run_summary.txt` and per-step exports under
`/tmp/smoke/output/steps/`.
