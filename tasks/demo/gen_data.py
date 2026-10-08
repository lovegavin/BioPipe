# tasks/demo/gen_data.py
"""Generate three CSVs that share a sample_id column.

phenotype.csv   sample_id, sex, batch, age, trait
expression.csv  sample_id, gene_A, gene_B, gene_C
methylation.csv sample_id, cpg_1, cpg_2, cpg_3

A couple of empty fields are injected into phenotype.csv to exercise
null handling in the reader. Deterministic given SEED.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "input"

N_SAMPLES = 200
SEED = 42


def _ids():
    return [f"S{i + 1:04d}" for i in range(N_SAMPLES)]


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(",".join(str(v) for v in row) + "\n")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ids = _ids()

    rng = random.Random(SEED)
    rows = []
    for sid in ids:
        sex = rng.choice(["M", "F"])
        batch = rng.choice([1, 2, 3])
        age = rng.randint(20, 80)
        base = 1.0 + (0.3 if sex == "M" else -0.3) + (age - 50) * 0.005
        base += rng.gauss(0, 0.2)
        rows.append([sid, sex, batch, age, round(base, 4)])

    # --- null tests ---
    rows[5][1] = ""    # sex, string column
    rows[5][3] = ""    # age, numeric column

    _write(OUT_DIR / "phenotype.csv", rows)

    rng = random.Random(SEED + 1)
    rows = [[sid] + [round(rng.gauss(5.0, 1.5), 4) for _ in range(3)]
            for sid in ids]
    _write(OUT_DIR / "expression.csv", rows)

    rng = random.Random(SEED + 2)
    rows = [[sid] + [round(rng.uniform(0.0, 1.0), 4) for _ in range(3)]
            for sid in ids]
    _write(OUT_DIR / "methylation.csv", rows)

    print(f"Wrote 3 files to {OUT_DIR}")


if __name__ == "__main__":
    main()