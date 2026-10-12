# tasks/ld_prune_demo/gen_data.py
"""Generate a VCF with correlated variants.

Variants are grouped into blocks of correlated sites. Within each
block, the same underlying allele is transmitted, so adjacent
variants are in high LD. Blocks are separated by independent
variants.
"""

from __future__ import annotations

import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "input" / "geno.vcf"

N_SAMPLES = 200
N_VARIANTS = 100
SEED = 42

# Variants whose 0-based index is a multiple of 3 begin a correlated
# block of 3 variants. The block shares one underlying factor with
# mild noise.
BLOCK_SIZE = 3


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

        # Pre-draw the underlying latent allele for each block.
        n_blocks = (N_VARIANTS + BLOCK_SIZE - 1) // BLOCK_SIZE
        latent = [
            [1 if rng.random() < 0.3 else 0 for _ in samples]
            for _ in range(n_blocks)
        ]

        for i in range(N_VARIANTS):
            pos = 10000 + i * 1000
            vid = f"rs{i + 1}"
            block = i // BLOCK_SIZE

            gts = []
            for s_idx, _ in enumerate(samples):
                if rng.random() < 0.01:
                    gts.append("./.")
                    continue
                # 90% chance to copy the latent allele, 10% noise.
                if rng.random() < 0.9:
                    a1 = latent[block][s_idx]
                    a2 = latent[block][s_idx]
                else:
                    a1 = 1 if rng.random() < 0.3 else 0
                    a2 = 1 if rng.random() < 0.3 else 0
                gts.append(f"{a1}/{a2}")

            f.write("\t".join(
                ["1", str(pos), vid, "A", "G", ".", ".", ".", "GT"] + gts
            ) + "\n")

    print(f"Wrote {N_VARIANTS} x {N_SAMPLES} to {OUT}")
    print(f"  blocks of {BLOCK_SIZE} correlated variants, "
          f"{n_blocks} blocks")


if __name__ == "__main__":
    main()