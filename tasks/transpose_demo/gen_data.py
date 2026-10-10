# tasks/transpose_demo/gen_data.py
"""Generate a small CSV with a sample id column and numeric features.

The sample id column is extracted as the sample dim's labels and
removed from data. Remaining columns enter the feature dim.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "input" / "data.csv"

N = 20
SEED = 42


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("sid,trait,age,gene_A,gene_B\n")
        for i in range(N):
            sid = f"S{i + 1:03d}"
            trait = round(rng.gauss(1.0, 0.3), 4)
            age = rng.randint(20, 80)
            ga = round(rng.gauss(5.0, 1.0), 4)
            gb = round(rng.gauss(5.0, 1.0), 4)
            f.write(f"{sid},{trait},{age},{ga},{gb}\n")

    print(f"Wrote {N} rows x 5 cols to {OUT}")


if __name__ == "__main__":
    main()