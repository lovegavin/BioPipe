"""Launch the built BioPipe Studio on loopback; no public-network binding."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=int(os.getenv("BIOPIPE_STUDIO_PORT", "8765")))
    parser.add_argument("--profile-dir", type=Path, help="Shared profile; relative paths are anchored to the user home")
    parser.add_argument("--workspace", type=Path, help="Explicit isolated workspace (disables legacy import)")
    parser.add_argument("--data-dir", type=Path, help="With --workspace only: data directory inside that workspace")
    parser.add_argument("--resolve-profile", action="store_true", help="Print resolved paths without starting or writing data")
    parser.add_argument("--frontend", type=Path, default=ROOT / "frontend/dist")
    args = parser.parse_args()
    from src.web.profile import make_settings, resolve_profile
    options = dict(profile_dir=args.profile_dir, workspace=args.workspace, data_dir=args.data_dir)
    try:
        profile = resolve_profile(ROOT, **options)
    except ValueError as error:
        parser.error(str(error))
    if args.resolve_profile:
        import json
        print(json.dumps(profile.as_dict(), ensure_ascii=False))
        return
    if not (args.frontend / "index.html").is_file():
        parser.error("Build the UI first: cd frontend && npm install && npm run build")
    if not 1 <= args.port <= 65535:
        parser.error("port must be between 1 and 65535")
    from src.web.api import create_app
    import uvicorn
    settings = make_settings(ROOT, args.frontend, **options)
    settings.instance_url = f"http://127.0.0.1:{args.port}"
    uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
