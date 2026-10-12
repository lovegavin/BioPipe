# tasks/pca_demo/gen_data.py
"""Generate a VCF with two subpopulations.

The first 100 samples have a low ALT allele frequency; the last 100
have a high one. PC1 should separate the two groups.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "input" / "geno.vcf"

N_SAMPLES = 200
N_VARIANTS = 500
SEED = 42

POP_A_P = 0.20
POP_B_P = 0.75


def _draw(rng, p):
    a = 1 if rng.random() < p else 0
    b = 1 if rng.random() < p else 0
    return a + b


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    samples = [f"S{i + 1:03d}" for i in range(N_SAMPLES)]

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("##fileformat=VCFv4.2\n")
        f.write('##FORMAT=<ID=GT,Number=1,Type=String,'
                'Description="Genotype">\n')
        header = ["#CHROM", "POS", "ID", "REF", "ALT",
                  "QUAL", "FILTER", "INFO", "FORMAT"]
        header.extend(samples)
        f.write("\t".join(header) + "\n")

        for i in range(N_VARIANTS):
            pos = 10000 + i * 100
            vid = f"rs{i + 1}"
            gts = []
            for s_idx, _ in enumerate(samples):
                if rng.random() < 0.01:
                    gts.append("./.")
                    continue
                p = POP_A_P if s_idx < 100 else POP_B_P
                g = _draw(rng, p)
                a1 = 1 if g >= 1 else 0
                a2 = 1 if g == 2 else 0
                gts.append(f"{a1}/{a2}")

            f.write("\t".join(
                ["1", str(pos), vid, "A", "G", ".", ".", ".", "GT"] + gts
            ) + "\n")

    print(f"Wrote {N_VARIANTS} x {N_SAMPLES} to {OUT}")
    print(f"  pop A (S001-S100): p={POP_A_P}")
    print(f"  pop B (S101-S200): p={POP_B_P}")


if __name__ == "__main__":
    main()