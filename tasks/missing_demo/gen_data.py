# tasks/missing_demo/gen_data.py
"""Generate a VCF with deliberate missingness on both axes.

Three variants and two samples have high missing rates, so a missing
filter applied along either dimension has something to remove.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "input" / "geno.vcf"

N_SAMPLES = 30
N_VARIANTS = 50
SEED = 42

HIGH_MISSING_SAMPLES = {"S002", "S017"}
HIGH_MISSING_VARIANTS = {7, 22, 41}


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
            p_var = 0.30 if i in HIGH_MISSING_VARIANTS else 0.01
            gts = []
            for sid in samples:
                p_sam = 0.40 if sid in HIGH_MISSING_SAMPLES else 0.0
                p = max(p_var, p_sam)
                if rng.random() < p:
                    gts.append("./.")
                    continue
                r = rng.random()
                gts.append("0/0" if r < 0.6 else "0/1" if r < 0.9 else "1/1")
            f.write("\t".join(
                ["1", str(pos), vid, "A", "G", ".", ".", ".", "GT"] + gts
            ) + "\n")

    print(f"Wrote {N_VARIANTS} x {N_SAMPLES} to {OUT}")
    print(f"  high-missingness samples:  {sorted(HIGH_MISSING_SAMPLES)}")
    print(f"  high-missingness variants: "
          f"{sorted(f'rs{i + 1}' for i in HIGH_MISSING_VARIANTS)}")


if __name__ == "__main__":
    main()