# tasks/concat_demo/gen_data.py
"""Generate three CSVs sharing a sample_id column, in different orders.

pheno.csv : sample_id, trait, age     (S01..S30)
expr.csv  : sample_id, gene_A, gene_B (S30..S01)
meth.csv  : sample_id, cpg_1, cpg_2   (shuffled)
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
IN = HERE / "input"

N = 30
SEED = 42


def _write(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(",".join(str(v) for v in r) + "\n")


def main():
    IN.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    ids = [f"S{i + 1:02d}" for i in range(N)]
    rev = list(reversed(ids))
    shuffled = ids[:]
    rng.shuffle(shuffled)

    _write(IN / "pheno.csv", [[
        sid,
        round(rng.gauss(1.0, 0.3), 4),
        rng.randint(20, 80)
    ] for sid in ids])

    _write(IN / "expr.csv", [[
        sid,
        round(rng.gauss(5.0, 1.0), 4),
        round(rng.gauss(5.0, 1.0), 4)
    ] for sid in rev])

    _write(IN / "meth.csv", [[
        sid,
        round(rng.uniform(0, 1), 4),
        round(rng.uniform(0, 1), 4)
    ] for sid in shuffled])

    print(f"Wrote 3 CSVs to {IN}")


if __name__ == "__main__":
    main()