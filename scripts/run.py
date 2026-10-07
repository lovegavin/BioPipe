# scripts/run.py
"""流水线入口：读 config.yaml 的 pipeline 字段，分派到对应 pipeline"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.pipelines import PIPELINES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    args = ap.parse_args()

    task_dir = Path(args.task).resolve()
    config_path = task_dir / "config.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"缺少 config.yaml。先运行: "
            f"python scripts/init_task.py --task {args.task}"
        )

    with open(config_path) as f:
        config = yaml.safe_load(f)

    pipeline_name = config.get("pipeline")
    if pipeline_name not in PIPELINES:
        raise ValueError(
            f"未知 pipeline: {pipeline_name}。可用: {list(PIPELINES.keys())}"
        )

    PIPELINES[pipeline_name].pipeline.run(task_dir)


if __name__ == "__main__":
    main()