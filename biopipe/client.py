"""Shared transport client for the CLI and MCP adapter."""
from pathlib import Path
import json
import time
from urllib.parse import urlsplit

import httpx


class ClientError(RuntimeError):
    def __init__(self, message, code="request_failed", details=None):
        super().__init__(message)
        self.code, self.details = code, details


def data_directory(profile=None, workspace=None, data_dir=None):
    from src.web.profile import resolve_profile
    return resolve_profile(Path(__file__).resolve().parents[1], profile_dir=profile, workspace=workspace, data_dir=data_dir).data_dir


def instances(directory):
    import psutil
    result = []
    for path in (Path(directory) / "agent/servers").glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            url = urlsplit(value["url"])
            if url.scheme != "http" or url.hostname not in ("127.0.0.1", "localhost") or url.username or url.password:
                continue
            try:
                if psutil.Process(value["pid"]).create_time() != value["created"]:
                    continue
            except psutil.Error:
                # A sandboxed agent may reach loopback while its process table
                # hides the desktop host. Authenticate that exact instance.
                try:
                    response = httpx.get(value["url"] + "/api/agent/identity",
                                         headers={"X-BioPipe-Bridge": value["secret"]},
                                         timeout=2, trust_env=False)
                    if not response.is_success or response.json().get("instance_id") != value["instance_id"]:
                        continue
                except (httpx.HTTPError, ValueError):
                    continue
            result.append(value)
        except (ValueError, KeyError, OSError, psutil.Error):
            continue
    return result


class Client:
    def __init__(self, directory, *, instance=None, name="external-agent", scopes=None):
        self.directory, self.name = Path(directory), name
        available = instances(directory)
        if instance:
            available = [item for item in available if item["instance_id"] == instance]
        if not available:
            raise ClientError("No running BioPipe Studio found in this profile. Start the desktop app or scripts/studio.py.", "not_connected")
        # Servers in one profile share the session command store. Select any live
        # endpoint unless the caller explicitly chooses an instance.
        self.instance = available[-1]
        self.http = httpx.Client(base_url=self.instance["url"], timeout=30, trust_env=False)
        value = self.http.post("/api/agent/connect", headers={"X-BioPipe-Bridge": self.instance["secret"]},
                               json={"name": name, "scopes": scopes or ["context", "edit"]})
        data = self.decode(value)
        self.http.headers["Authorization"] = "Bearer " + data["token"]

    @staticmethod
    def decode(response):
        try:
            value = response.json()
        except ValueError:
            raise ClientError("Studio returned an invalid response")
        if not response.is_success:
            raise ClientError(value.get("message") or str(value.get("detail", response.status_code)),
                              value.get("code", "request_failed"), value.get("details"))
        return value

    def request(self, path, payload=None):
        response = self.http.get("/api/agent" + path) if payload is None else self.http.post(
            "/api/agent" + path, json=payload, timeout=660 if path == "/plugins/install" else 30)
        return self.decode(response)

    def sessions(self):
        return self.request("/sessions")

    def session(self, selected=None):
        if selected:
            return selected
        from datetime import datetime, timezone
        values = self.sessions()
        live = [value for value in values if (datetime.now(timezone.utc) - datetime.fromisoformat(value["updated_at"])).total_seconds() < 20]
        values = live or values
        if len(values) != 1:
            raise ClientError("Select a canvas with --session; use sessions list to inspect available windows.", "ambiguous_session",
                              {"sessions": [{"id": v["id"], "name": v["name"]} for v in values]})
        return values[0]["id"]

    def context(self, session=None, scope="selection"):
        return self.request(f"/sessions/{self.session(session)}/context?scope={scope}")

    def close(self):
        try:
            self.http.post("/api/agent/disconnect", json={}, timeout=2)
        except httpx.HTTPError:
            pass
        self.http.close()
