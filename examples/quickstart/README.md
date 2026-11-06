# Quickstart example: VHH / 1MEL interface

A minimal, real-data workflow used by `QUICKSTART.md` at the repository root and by the
`BioPipe-Quickstart-*.zip` release asset. It runs in a few seconds on a laptop CPU
and produces two exported CSV tables.

## Files

| Path | Description |
| --- | --- |
| `data/vhh_1mel.pdb` | RCSB entry [1MEL](https://doi.org/10.2210/pdb1MEL/pdb), 3,908 atoms, chains A/B (VHH) and L/M (lysozyme). Byte-identical to `https://files.rcsb.org/download/1MEL.pdb`, sha256 `321aa847a20535c018b12cf340d2e057628dce42b4005c185916dd17bdd24de4`. |
| `data/vhh.fasta` | VHH sequence of chain A (132 aa, from the deposited SEQRES), sha256 `7d148d84823f753a2ec06c8ef4db206efd6b057bedad6bac476fcbfb994b4fa5`. |
| `vhh_interface.route.json` | Self-contained graph (schema 2): two sources, `structure_interface_core`, `sequence_liability_scan`, two `export_results` nodes. |

## Run

```bash
python -m biopipe --workspace "$PWD" run examples/quickstart/vhh_interface.route.json --wait
```

`base_dir` is `examples/quickstart`, resolved against the workspace root. Exports are
written to `output/artifacts/exports/<hash>/`.

## Expected results

| Quantity | Value |
| --- | --- |
| Interface residues | 88 |
| Core | 52 |
| Rim | 36 |
| Liabilities | 10 (5 oxidation, 3 isomerization, 2 deamidation) |

`interface_residues.csv` has 88 rows with columns
`residue,delta_sasa,isolated_sasa,buried_fraction,is_core`; `liabilities.csv` has 10
rows with columns `liability,position,severity_code,motif_length`.

## Data provenance

1MEL is a public PDB deposition (DOI [10.2210/pdb1MEL/pdb](https://doi.org/10.2210/pdb1MEL/pdb)).
The FASTA file is derived from its chain A SEQRES record; no synthetic data is used.
