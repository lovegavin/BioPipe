# tasks/regress_demo/gen_data.py
"""Generate a wide CSV with a response, two covariates, and 20 features.

To exercise the failure paths, three predictors are crafted:

    rs1  carries a real effect       (normal fit)
    rs2  is constant across samples  (constant predictor)
    rs3  is perfectly separated      (perfect separation, binary only)

The response is continuous by default, so rs3 only fails when the
user forces method: logit or when the trait is binary.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
IN = HERE / "input"

N = 200
N_FEATURES = 20
SEED = 42


def main() -> None:
    IN.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    age = [rng.randint(20, 80) for _ in range(N)]
    sex = [rng.choice([0, 1]) for _ in range(N)]

    features: list[list[float]] = []

    # rs1: real signal
    p1 = 0.3
    rs1 = []
    for _ in range(N):
        a1 = 1 if rng.random() < p1 else 0
        a2 = 1 if rng.random() < p1 else 0
        rs1.append(a1 + a2)
    features.append(rs1)

    # rs2: constant column (always 0)
    features.append([0.0] * N)

    # rs3: perfect separator for a synthetic binary outcome
    # (not used with the continuous trait, but present in data)
    features.append([1.0 if i % 2 == 0 else 0.0 for i in range(N)])

    # rs4..rs20: noise
    for v in range(3, N_FEATURES):
        p = rng.uniform(0.1, 0.5)
        col = []
        for _ in range(N):
            a1 = 1 if rng.random() < p else 0
            a2 = 1 if rng.random() < p else 0
            col.append(a1 + a2)
        features.append(col)

    # Continuous trait: rs1 has effect, rs2 is constant, so has no effect
    trait = [
        1.0 + 0.4 * features[0][i] + 0.02 * age[i] + rng.gauss(0, 0.5)
        for i in range(N)
    ]
    missing_idx = set(rng.sample(range(N), 5))

    header = ["sample_id", "age", "sex", "trait"]
    header += [f"rs{v + 1}" for v in range(N_FEATURES)]

    with open(IN / "data.csv", "w", encoding="utf-8") as f:
        f.write(",".join(header) + "\n")
        for i in range(N):
            row = [
                f"S{i + 1:03d}",
                age[i],
                sex[i],
                "" if i in missing_idx else round(trait[i], 4),
            ]
            row += [features[v][i] for v in range(N_FEATURES)]
            f.write(",".join(str(v) for v in row) + "\n")

    print(f"Wrote {N} rows x {len(header)} cols to {IN / 'data.csv'}")
    print(f"  response   : trait")
    print(f"  covariates : age, sex")
    print(f"  rs1        : real effect")
    print(f"  rs2        : constant column (should be skipped)")
    print(f"  rs3        : parity column")
    print(f"  rs4..rs20  : noise")


if __name__ == "__main__":
    main()