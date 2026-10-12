# tasks/maf_demo/gen_data.py
"""Generate a VCF with a range of allele frequencies.

Allele frequency per variant is drawn uniformly from [0, 0.5] so that
a MAF threshold of 0.05 has something to remove.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "input" / "geno.vcf"

N_SAMPLES = 100
N_VARIANTS = 200
SEED = 42


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
            # Draw MAF from a range that produces both rare and common
            # variants.
            maf = rng.uniform(0.0, 0.5)
            p_alt = maf  # allele frequency of ALT

            pos = 10000 + i * 1000
            vid = f"rs{i + 1}"
            gts = []
            for _ in samples:
                if rng.random() < 0.01:
                    gts.append("./.")
                    continue
                # Sample two alleles with probability p_alt.
                a1 = 1 if rng.random() < p_alt else 0
                a2 = 1 if rng.random() < p_alt else 0
                gts.append(f"{a1}/{a2}")
            f.write("\t".join(
                ["1", str(pos), vid, "A", "G", ".", ".", ".", "GT"] + gts
            ) + "\n")

    print(f"Wrote {N_VARIANTS} x {N_SAMPLES} to {OUT}")
    print("  MAF drawn uniformly from [0, 0.5]")


if __name__ == "__main__":
    main()