"""Real loopback HTTP, CLI processes and MCP stdio interoperability."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading
import time

import httpx
import uvicorn

from src.web.api import create_app
from src.web.service import Settings


def test_cli_and_mcp_share_context_transactions_and_permissions(tmp_path):
    root = Path(__file__).resolve().parents[1]
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    url = f"http://127.0.0.1:{sock.getsockname()[1]}"
    settings = Settings(root=tmp_path, data_dir=tmp_path / ".studio", dist_dir=root / "frontend/dist",
                        testing=True, code_root=root, instance_url=url)
    app = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(.05)
        assert server.started
        with httpx.Client(base_url=url, trust_env=False) as ui:
            bootstrap = ui.get("/api/bootstrap").json()
            ui.headers["X-Studio-Token"] = bootstrap["token"]
            state = ui.post("/api/agent/sessions", json={"workspace": {
                "schema_version": 1, "active_id": "main", "documents": [{"id": "main", "graph": bootstrap["demo"]}]}}).json()
            session = state["id"]
            ui.post(f"/api/agent/sessions/{session}/presence", json={"document_id": "main", "nodes": ["pca"], "edges": []}).raise_for_status()
            command = [sys.executable, "-m", "biopipe", "--workspace", str(tmp_path), "--session", session]
            result = subprocess.run(command + ["context", "get"], cwd=root, capture_output=True, encoding="utf-8", timeout=20)
            assert result.returncode == 0, result.stderr
            context = json.loads(result.stdout)
            assert context["selection"]["nodes"] == ["pca"]
            assert context["name"] == bootstrap["demo"]["name"]

            async def exercise_mcp():
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client
                config = StdioServerParameters(command=sys.executable, args=["-m", "biopipe", "--workspace", str(tmp_path), "mcp"],
                                               cwd=str(root), env={**os.environ, "PYTHONIOENCODING": "utf-8"})
                async with stdio_client(config) as (reader, writer):
                    async with ClientSession(reader, writer) as client:
                        await client.initialize()
                        assert "biopipe_apply" in {t.name for t in (await client.list_tools()).tools}
                        value = await client.call_tool("biopipe_context", {"session_id": session})
                        assert not value.isError
                        assert json.loads(value.content[0].text)["selection"]["nodes"] == ["pca"]
                        resource = await client.read_resource(f"biopipe://sessions/{session}/selection")
                        assert json.loads(resource.contents[0].text)["document_id"] == "main"
                        payload = {"session_id": session, "document_id": "main", "expected_revision": 0,
                                   "request_id": "mcp-test-batch", "commands": [
                                       {"op": "update_node", "id": "pca", "patch": {"params": {"dim": "feature", "n_components": 3, "output": "pcs"}}},
                                       {"op": "configure", "patch": {"name": "Agent edited route"}}]}
                        changed = await client.call_tool("biopipe_apply", payload)
                        assert not changed.isError, changed
                        denied = await client.call_tool("biopipe_run", {"session_id": session, "document_id": "main", "expected_revision": 1})
                        assert denied.isError
                        assert "capability" in denied.content[0].text
            asyncio.run(exercise_mcp())
            changed = ui.get(f"/api/agent/sessions/{session}").json()
            assert changed["revision"] == 1
            assert changed["history"]["main"]["undo"] == 1
            result = subprocess.run(command + ["graph", "undo", "--document", "main", "--expected-revision", "1"],
                                    cwd=root, capture_output=True, encoding="utf-8", timeout=20)
            assert result.returncode == 0, result.stderr
            restored = json.loads(result.stdout)
            assert restored["workspace"]["documents"][0]["graph"]["name"] == bootstrap["demo"]["name"]
            result = subprocess.run(command + ["graph", "undo", "--document", "main", "--expected-revision", "1"],
                                    cwd=root, capture_output=True, encoding="utf-8", timeout=20)
            assert result.returncode == 3
            assert json.loads(result.stderr)["error"]["code"] == "revision_conflict"
    finally:
        server.should_exit = True
        thread.join(10)
        sock.close()
    assert not thread.is_alive()
