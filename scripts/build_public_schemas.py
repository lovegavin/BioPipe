"""Regenerate checked-in public JSON schemas from the live protocol models."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from biopipe_sdk.protocol import Descriptor
from src.web.models import Graph, Workspace


def main():
    directory = ROOT / "biopipe_sdk/schemas"
    directory.mkdir(parents=True, exist_ok=True)
    for name, cls in {"operator": Descriptor, "graph": Graph, "workspace": Workspace}.items():
        (directory / f"{name}.json").write_text(
            json.dumps(cls.model_json_schema(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Public schemas generated")


if __name__ == "__main__":
    main()
