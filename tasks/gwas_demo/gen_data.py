import random
from pathlib import Path

random.seed(42)
base = Path(".")

# --- 读 geno.vcf 里的样本 ID ---
geno_samples = []
with open(base / "geno.vcf") as f:
    for line in f:
        if line.startswith("#CHROM"):
            geno_samples = line.strip().split("\t")[9:]
            break
print(f"geno samples: {len(geno_samples)}")

# --- 读样本面板 ---
info = {}
with open(base / "integrated_call_samples_v3.20130502.ALL.panel") as f:
    next(f)  # header
    for line in f:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 4:
            continue
        info[parts[0]] = {
            "pop": parts[1],
            "super_pop": parts[2],
            "sex": parts[3],          # "male" / "female"
        }

matched = [s for s in geno_samples if s in info]
print(f"matched: {len(matched)}")

# --- 表型 ---
with open(base / "phenotype.csv", "w") as f:
    f.write("sample_id,trait_value\n")
    for s in matched:
        sex_effect = 0.2 if info[s]["sex"] == "male" else -0.2
        v = 1.0 + sex_effect + random.gauss(0, 0.5)
        f.write(f"{s},{v:.6f}\n")

# --- 协变量 ---
batch_map = {"EUR": 1, "AFR": 2, "EAS": 3, "SAS": 4, "AMR": 5}
with open(base / "covariates.csv", "w") as f:
    f.write("sample_id,sex,batch\n")
    for s in matched:
        sex = 1 if info[s]["sex"] == "male" else 0
        batch = batch_map.get(info[s]["super_pop"], 0)
        f.write(f"{s},{sex},{batch}\n")

print("phenotype.csv 和 covariates.csv 已生成")