# tasks/correction_demo/gen_data.py
"""Generate a regression-like result table.

Two variants carry real effects on the phenotype; the rest are noise.

The demo runs a full regress, then applies correction twice: once
with Bonferroni and once with FDR.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
IN = HERE / "input"

N_SAMPLES = 500
N_VARIANTS = 1000
SEED = 42


def main() -> None:
    IN.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    # Genotypes
    geno = []
    for v in range(N_VARIANTS):
        p = rng.uniform(0.05, 0.5)
        col = []
        for _ in range(N_SAMPLES):
            a1 = 1 if rng.random() < p else 0
            a2 = 1 if rng.random() < p else 0
            col.append(a1 + a2)
        geno.append(col)

    # Phenotype: rs1 and rs2 have real effects
    y = []
    for i in range(N_SAMPLES):
        val = 1.0
        val += 0.5 * geno[0][i]
        val += 0.4 * geno[1][i]
        val += rng.gauss(0, 1.0)
        y.append(round(val, 4))

    # Write CSV
    header = ["sample_id", "trait"] + [f"rs{v + 1}" for v in range(N_VARIANTS)]
    with open(IN / "data.csv", "w", encoding="utf-8") as f:
        f.write(",".join(header) + "\n")
        for i in range(N_SAMPLES):
            row = [f"S{i + 1:04d}", y[i]]
            row += [geno[v][i] for v in range(N_VARIANTS)]
            f.write(",".join(str(v) for v in row) + "\n")

    print(f"Wrote {N_SAMPLES} x {N_VARIANTS} to {IN / 'data.csv'}")
    print(f"  rs1 and rs2 have real effects on trait")


if __name__ == "__main__":
    main()