"""Private desktop backend. The host owns stdin and the complete process tree."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import sys
import threading

CODE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE_ROOT))


def bind_loopback(preferred_port: int = 0) -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Retain ownership from allocation through uvicorn startup (no port race).
    if os.name == "nt":
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        listener.bind(("127.0.0.1", preferred_port))
    except OSError:
        if not preferred_port:
            listener.close()
            raise
        listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    listener.setblocking(False)
    return listener


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--frontend", type=Path, default=CODE_ROOT / "frontend/dist")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--wait-for-host", action="store_true")
    args = parser.parse_args()
    # The host first attaches us to its Windows Job Object, then releases startup.
    if args.wait_for_host and sys.stdin.readline().strip() != "start":
        return
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    data_dir = workspace / ".studio"
    os.environ["MPLCONFIGDIR"] = str(data_dir / "matplotlib")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    from src.web.api import create_app
    from src.web.service import Settings
    import uvicorn

    if not (args.frontend / "index.html").is_file():
        parser.error("Frontend index.html is missing")
    settings = Settings(workspace, data_dir, args.frontend.resolve(),
                        code_root=CODE_ROOT, desktop=True)
    app = create_app(settings)
    finished = threading.Event()
    with bind_loopback(args.port) as listener:
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                             access_log=False, timeout_graceful_shutdown=3))

        def announce():
            while not server.started and not finished.wait(.05):
                pass
            if server.started and not finished.is_set():
                print("BIOPIPE_READY " + json.dumps({"url": f"http://127.0.0.1:{port}",
                                                     "pid": os.getpid()}), flush=True)

        def watch_host():
            # EOF also shuts down if the parent exits before sending shutdown.
            for line in sys.stdin:
                if line.strip() == "shutdown":
                    break
            server.should_exit = True

        threading.Thread(target=announce, daemon=True).start()
        threading.Thread(target=watch_host, daemon=True).start()
        try:
            server.run(sockets=[listener])
        finally:
            finished.set()


if __name__ == "__main__":
    main()
