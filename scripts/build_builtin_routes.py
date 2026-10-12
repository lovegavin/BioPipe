"""Build the shipped route manifest from the four upstream example workflows.

Run after adapting operators/contracts, then review the JSON diff. Startup loads
this manifest; it does not need git, the examples directory, or a network call.
"""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="ab439ab9af3a36220941d6a8b27c580a268b7c95")
    args = parser.parse_args()
    from src.task import STEPS
    from src.task.operator_catalog import build_catalog
    from src.web.graph import import_manifest
    from src.web.routes import prepare_interface, check_interface
    catalog = build_catalog(STEPS)
    routes = []
    for key, name in (("gwas", "GWAS"), ("rnaseq_de", "RNA-seq DE"),
                      ("proteomics_de", "Proteomics DE"), ("survival", "生存分析")):
        source = f"tasks/{key}_demo/task.yaml"
        text = subprocess.check_output(["git", "show", f"{args.ref}:{source}"], cwd=ROOT).decode("utf-8")
        # PyYAML's YAML 1.1 resolver treats upstream's `1e6` as text. Normalize
        # only declared numeric parameters before emitting the typed manifest.
        raw = yaml.safe_load(text)
        specs = {item["name"]: item for item in catalog["operators"]}
        for step in raw["steps"]:
            params = step.get("params", {})
            for field in specs[step["name"]]["parameters"]:
                value = params.get(field["key"])
                if field["type"] in ("number", "integer") and isinstance(value, str):
                    params[field["key"]] = float(value)
        text = yaml.safe_dump(raw, allow_unicode=True)
        graph = import_manifest(text, f".studio/builtin-inputs/{key}", catalog, ROOT)
        graph.name = name
        # Lay out every branch by dependency depth; no operator-order wrapping.
        levels, rows = {}, {}
        for node in graph.nodes:
            parents = [edge.source for edge in graph.edges if edge.target == node.id]
            level = max((levels[parent] + 1 for parent in parents), default=0)
            levels[node.id] = level
            row = rows.get(level, 0); rows[level] = row + 1
            node.position.x, node.position.y = 70 + 290 * level, 100 + 210 * row
        graph = prepare_interface(graph, catalog, ROOT)
        check_interface(graph, catalog)
        routes.append({"id": "route_" + sha256(("biopipe/builtin/" + key).encode()).hexdigest()[:12],
                       "version": 1, "name": name, "graph": graph.model_dump(mode="json")})
    destination = ROOT / "src/web/builtin_routes.json"
    destination.write_text(json.dumps({"schema_version": 1, "source_commit": args.ref, "routes": routes},
                                     ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"path": str(destination), "routes": [{"name": r["name"], "nodes": len(r["graph"]["nodes"]),
                      "inputs": len(r["graph"]["interface"]["inputs"]), "outputs": len(r["graph"]["interface"]["outputs"])}
                      for r in routes]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
