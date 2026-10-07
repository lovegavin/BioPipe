# scripts/gen_all_data.py
"""生成全部 6 个客户的数据"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TASKS = [
    "task_001_userA_GWAS",
    "task_002_userB_GWAS",
    "task_003_userC_GWAS",
    "task_004_userD_GWAS",
    "task_005_userE_GWAS",
    "task_006_userF_GWAS",
]


def main():
    for t in TASKS:
        script = ROOT / "tasks" / t / "make_data.py"
        print(f"\n{'='*60}\n{t}\n{'='*60}")
        subprocess.run([sys.executable, str(script)], check=True)


if __name__ == "__main__":
    main()