# tasks/hwe_demo/gen_data.py
"""Generate a VCF with a mix of HWE-compliant and HWE-violating variants.

Ten variants are deliberately skewed: some have excess heterozygotes,
some have deficient heterozygotes. The remaining variants are drawn
under HWE.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "input" / "geno.vcf"

N_SAMPLES = 200
N_VARIANTS = 100
SEED = 42

HWE_VIOLATORS = set(range(0, 20, 2))


def _hwe_genotype(rng, p):
    a = 1 if rng.random() < p else 0
    b = 1 if rng.random() < p else 0
    return a + b


def _skewed_genotype(rng, p, mode):
    if mode == "excess":
        return 1 if rng.random() < 0.9 else _hwe_genotype(rng, p)
    return rng.choice([0, 2])


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
            pos = 10000 + i * 1000
            vid = f"rs{i + 1}"
            p = rng.uniform(0.1, 0.5)

            gts = []
            for _ in samples:
                if rng.random() < 0.01:
                    gts.append("./.")
                    continue
                if i in HWE_VIOLATORS:
                    mode = "excess" if (i // 2) % 2 == 0 else "deficient"
                    g = _skewed_genotype(rng, p, mode)
                else:
                    g = _hwe_genotype(rng, p)
                a1 = 1 if g >= 1 else 0
                a2 = 1 if g == 2 else 0
                gts.append(f"{a1}/{a2}")

            f.write("\t".join(
                ["1", str(pos), vid, "A", "G", ".", ".", ".", "GT"] + gts
            ) + "\n")

    print(f"Wrote {N_VARIANTS} x {N_SAMPLES} to {OUT}")
    print(f"  HWE-violating variants: "
          f"{sorted(f'rs{i + 1}' for i in HWE_VIOLATORS)}")


if __name__ == "__main__":
    main()