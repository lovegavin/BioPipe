"""Build this independent v3 operator library using the installed BioPipe SDK."""
import argparse
import json
from pathlib import Path
from biopipe.library_bundle import build_bundle

if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--output", type=Path, default=root / "dist")
    args = parser.parse_args()
    print(json.dumps(build_bundle(root, args.output, args.version), indent=2))
