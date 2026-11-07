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
            except psutil.NoSuchProcess:
                continue
            except psutil.Error:
                pass  # The authenticated handshake also works with a hidden process table.
            try:
                response = httpx.get(value["url"] + "/api/agent/identity",
                                     headers={"X-Operon-Bridge": value["secret"]},
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
    def __init__(self, directory, *, instance=None, name="external-agent", scopes=None, auto_start=False, workspace=None, require_api=0):
        self.directory, self.name = Path(directory), name
        available = instances(directory)
        available = [value for value in available if value.get('api_version', 0) >= require_api]
        if instance:
            available = [item for item in available if item["instance_id"] == instance]
        if not available and auto_start and not instance:
            from .headless import ensure_service
            available = ensure_service(directory, workspace=workspace, require_api=require_api)
        if not available:
            raise ClientError("No running Operon service found in this profile. Start operon serve or open Operon.", "not_connected")
        # Servers in one profile share the session command store. Select any live
        # endpoint unless the caller explicitly chooses an instance.
        self.instance = available[-1]
        self.scopes = scopes or ["context", "edit"]
        self.workspace = workspace
        self.http = httpx.Client(base_url=self.instance["url"], timeout=30, trust_env=False)
        self.connect()

    def connect(self):
        value = self.http.post("/api/agent/connect", headers={"X-Operon-Bridge": self.instance["secret"]},
                               json={"name": self.name, "scopes": self.scopes})
        data = self.decode(value)
        self.http.headers["Authorization"] = "Bearer " + data["token"]
        return data

    @staticmethod
    def decode(response):
        try:
            value = response.json()
        except ValueError:
            raise ClientError("Operon returned an invalid response")
        if not response.is_success:
            raise ClientError(value.get("message") or str(value.get("detail", response.status_code)),
                              value.get("code", "request_failed"), value.get("details"))
        return value

    def status(self):
        return {"connected": True, "url": str(self.http.base_url), "scopes": list(self.scopes),
                "workspace": str(self.workspace) if self.workspace else "",
                "instance_id": self.instance.get("instance_id") if self.instance else ""}

    def restart(self):
        """Re-discover the live bridge after Operon restarted and re-authenticate.

        A restart publishes a new discovery record with a new instance id, secret
        and connection table. The previous token is unknown to it, and posting to
        the old secret fails, so the client must reload discovery before it can
        mint a token again.
        """
        available = instances(self.directory)
        if not available:
            raise ClientError("No running Operon service found in this profile. Start operon serve or open Operon.", "not_connected")
        previous = self.instance.get("url") if self.instance else ""
        same = [value for value in available if value.get("url") == previous]
        self.instance = (same or available)[-1]
        self.http.close()
        self.http = httpx.Client(base_url=self.instance["url"], timeout=30, trust_env=False)
        return self.connect()

    def request(self, path, payload=None):
        route = '/api' + path if path.startswith('/v1/') else '/api/agent' + path
        preparation = path == '/v1/workflows/prepare-environment'
        timeout = 1800 if preparation else 660 if path == '/plugins/install' else 120
        response = self.http.get(route) if payload is None else self.http.post(
            route, json=payload, timeout=timeout)
        # Preparation is an explicit mutation. Do not transparently replay it;
        # in particular, denied install scope must not become an auto-upgrade.
        if response.status_code == 403 and not preparation:
            try:
                self.restart()
            except (ClientError, httpx.HTTPError):
                return self.decode(response)
            response = self.http.get(route) if payload is None else self.http.post(
                route, json=payload, timeout=timeout)
        return self.decode(response)

    def download(self, path, destination, payload=None):
        """Stream an explicitly selected artifact/bundle without loading it in RAM."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        import os, tempfile
        fd, temporary = tempfile.mkstemp(prefix=destination.name + '.', dir=destination.parent)
        size = 0
        try:
            with os.fdopen(fd, 'wb') as stream:
                route = '/api' + path if path.startswith('/v1/') else '/api/agent' + path
                with self.http.stream('POST' if payload is not None else 'GET', route, json=payload, timeout=120) as response:
                    if not response.is_success:
                        response.read(); self.decode(response)
                    for chunk in response.iter_bytes(1024 * 1024):
                        stream.write(chunk); size += len(chunk)
            os.replace(temporary, destination)
            return {'path': str(destination.resolve()), 'bytes': size}
        finally:
            Path(temporary).unlink(missing_ok=True)

    def sessions(self):
        return self.request("/sessions")

    def session(self, selected=None):
        if selected:
            return selected
        from datetime import datetime, timezone
        values = self.sessions()
        live = [value for value in values if (datetime.now(timezone.utc) - datetime.fromisoformat(value["updated_at"])).total_seconds() < 20]
        values = live or values
        if not values:
            raise ClientError('No canvas is open. Use workflow commands or operon_submit for headless analysis.', 'no_active_session')
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
