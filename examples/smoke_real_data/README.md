# Real-data example inputs

Two files, both real public data, no downloads and no model weights:

- `input/vhh_1mel.pdb` — RCSB 1MEL, 3908 atoms; VHH domains `A`,`B` and
  lysozyme `L`,`M`.
- `input/vhh.fasta` — the real 132-aa chain `A` sequence (Kabsch VHH).

This directory deliberately contains **no ready-made route**: the quickstart
asks an agent to design the graph from the operator catalog, adjust it on
request, validate and submit it. A reference implementation for regression
tests lives in `tests/fixtures/smoke_route/` and must not be read when solving
the exercise.

Expected result of the two-step design (interface core/rim + sequence
liabilities): 99 interface residues (58 core, 41 rim) and 10 liabilities
(5 oxidation, 3 isomerization, 2 deamidation), about 3 seconds on CPU.
