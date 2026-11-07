# Operon Operator Library v4.0.3

**Minimum application:** 2.6.0 (frontend 2.6.0)

This patch completes the onboarding pack shipped with v4.0.2. The operator set is
unchanged: **717 operators, 101 Readers, 7 packages, 24 built-in routes, protocol
v3**. Execution identity, contracts and workflow parameters are identical, so
existing workflows do not need to be repinned.

## What changed

- `examples/quickstart/data/vhh.fasta` is now tracked. The repository `.gitignore`
  excludes `*.fasta`, so v4.0.2's `Operon-Quickstart-v4.0.2.zip` contained the
  structure input but not the sequence input, and the bundled route could not run
  before repointing both sources by hand.
- `.gitignore` now carries an explicit `!examples/quickstart/data/vhh.fasta`
  exception so the public 132 aa VHH sequence stays in the example pack.
- Version files (`library/release.json`, `library/pyproject.toml`) move to 4.0.3.

## Verification

- `Operon-Quickstart-v4.0.3.zip` contains 8 entries: both QUICKSTART documents,
  `quickstart/README.md`, `quickstart/vhh_interface.route.json`,
  `quickstart/data/vhh_1mel.pdb` (361,017 B), `quickstart/data/vhh.fasta` (145 B).
- The route itself is unchanged and was validated end to end: job complete 4/4,
  `structure_interface_core` 88/52/36, `sequence_liability_scan` 10 sites
  (5 oxidation, 3 isomerization, 2 deamidation), `interface_residues.csv` 88 rows,
  `liabilities.csv` 10 rows.
- Registry: 717 operators / 101 Readers / 7 packages / 24 routes, errors [].

## Assets

- `Operon-Library-v4.0.3-Linux.operon-library.zip`
- `Operon-Library-v4.0.3-Windows.operon-library.zip`
- `operon_builtin_library-4.0.3-py3-none-any.whl`
- `Operon-Quickstart-v4.0.3.zip`
- `SHA256SUMS.txt`
- `verification-ubuntu-latest.json`, `verification-windows-latest.json`
