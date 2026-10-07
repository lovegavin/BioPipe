# scripts/init_task.py
"""扫描 task 目录 → 生成 config.yaml（分派到对应 pipeline 的 init）"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipelines import PIPELINES


def infer_pipeline(task_dir):
    """从目录名末段解析 pipeline 名, 如 task_001_userA_GWAS -> gwas"""
    return Path(task_dir).name.split("_")[-1].lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--pipeline", default=None,
                    help="不指定则从 task 目录名末段解析")
    args = ap.parse_args()

    task_dir = Path(args.task).resolve()
    pipeline_name = args.pipeline or infer_pipeline(task_dir)

    if pipeline_name not in PIPELINES:
        raise ValueError(
            f"未知 pipeline: {pipeline_name}。可用: {list(PIPELINES.keys())}"
        )

    mod = PIPELINES[pipeline_name]
    input_section = mod.init.init_from_input_dir(task_dir)

    config = mod.config.default_config()
    config["input"] = input_section

    out_path = task_dir / "config.yaml"
    with open(out_path, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False, allow_unicode=True)

    print(f"生成配置: {out_path}")


if __name__ == "__main__":
    main()