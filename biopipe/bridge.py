"""Loopback agent gateway. CLI and MCP use exactly these canvas commands."""
import asyncio
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from biopipe.documents import CommandError, DocumentHub
from src.web.storage import atomic_json
from src.web.models import Graph
from src.web.graph import compile_graph


class Bridge:
    def __init__(self, app, service, studio_token):
        self.app, self.service, self.studio_token = app, service, studio_token
        self.hub = DocumentHub(service)
        self.id, self.secret = uuid.uuid4().hex, secrets.token_urlsafe(32)
        self.connections = {}
        self.path = service.directory / "agent/servers" / f"{self.id}.json"
        self.register_routes()

    def publish(self, url):
        if not url:
            return
        import psutil
        atomic_json(self.path, {"protocol_version": 1, "instance_id": self.id, "url": url,
                               "pid": os.getpid(), "created": psutil.Process().create_time(), "secret": self.secret})
        os.chmod(self.path, 0o600)

    def close(self):
        self.path.unlink(missing_ok=True)

    def actor(self, request, capability):
        if hmac.compare_digest(request.headers.get("x-studio-token", ""), self.studio_token):
            return "user"
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        value = self.connections.get(hashlib.sha256(token.encode()).hexdigest())
        if not value or capability not in value["scopes"]:
            raise HTTPException(403, f"Agent connection requires '{capability}' capability")
        return "agent:" + value["name"]

    def register_routes(self):
        app, hub, service = self.app, self.hub, self.service

        @app.get("/api/agent/identity")
        def identity(request: Request):
            if not hmac.compare_digest(request.headers.get("x-biopipe-bridge", ""), self.secret):
                raise HTTPException(403, "Invalid instance discovery credential")
            return {"instance_id": self.id}

        @app.exception_handler(CommandError)
        async def command_error(request, error):
            return JSONResponse({"code": error.code, "message": str(error), "details": error.details}, status_code=error.status)

        @app.post("/api/agent/connect")
        def connect(request: Request, payload: dict):
            if not hmac.compare_digest(request.headers.get("x-biopipe-bridge", ""), self.secret):
                raise HTTPException(403, "Use the local instance discovery file to connect")
            scopes = payload.get("scopes", ["context", "edit"])
            if not isinstance(scopes, list) or not set(scopes) <= {"context", "edit", "run", "plugins"}:
                raise CommandError("invalid_scopes", "Unknown connection capabilities")
            token = secrets.token_urlsafe(32)
            key = hashlib.sha256(token.encode()).hexdigest()
            self.connections[key] = {"name": str(payload.get("name", "external-agent"))[:80], "scopes": scopes}
            return {"token": token, "scopes": scopes, "instance_id": self.id}

        @app.get("/api/agent/connections")
        def connections(request: Request):
            self.actor(request, "context")
            return [{"id": key, **value} for key, value in self.connections.items()]

        @app.post("/api/agent/disconnect")
        def disconnect(request: Request):
            self.actor(request, "context")
            token = request.headers.get("authorization", "").removeprefix("Bearer ")
            self.connections.pop(hashlib.sha256(token.encode()).hexdigest(), None)
            return {"disconnected": True}

        @app.post("/api/agent/connections/revoke")
        def revoke(request: Request, payload: dict):
            if not hmac.compare_digest(request.headers.get("x-studio-token", ""), self.studio_token):
                raise HTTPException(403, "Only the desktop user can revoke another connection")
            self.connections.pop(payload.get("id"), None)
            return {"revoked": True}

        @app.get("/api/agent/sessions")
        def sessions(request: Request):
            self.actor(request, "context")
            return hub.list()

        @app.post("/api/agent/sessions")
        def create_session(request: Request, payload: dict):
            self.actor(request, "edit")
            return hub.create(payload["workspace"], payload.get("name", "BioPipe Studio"))

        @app.get("/api/agent/sessions/{session}")
        def snapshot(session: str, request: Request):
            self.actor(request, "context")
            return hub.get(session)

        @app.post("/api/agent/sessions/{session}/sync")
        def sync(session: str, request: Request, payload: dict):
            if self.actor(request, "edit") != "user":
                raise HTTPException(403, "Agents must use graph commands instead of replacing the UI workspace")
            return hub.sync(session, payload["workspace"], payload["expected_revision"])

        @app.post("/api/agent/sessions/{session}/presence")
        def presence(session: str, request: Request, payload: dict):
            if self.actor(request, "edit") != "user":
                raise HTTPException(403, "Only the UI publishes user selection")
            return hub.presence(session, payload)

        @app.get("/api/agent/sessions/{session}/context")
        def context(session: str, request: Request, scope: str = "selection"):
            return hub.context(session, scope, self.actor(request, "context"))

        @app.post("/api/agent/sessions/{session}/apply")
        def apply(session: str, request: Request, payload: dict):
            actor = self.actor(request, "edit")
            try:
                return hub.apply(session, payload["document_id"], payload["expected_revision"], payload["commands"],
                                 actor, payload.get("request_id"))
            except (KeyError, ValidationError) as error:
                raise CommandError("invalid_commands", str(error)) from error

        @app.post("/api/agent/sessions/{session}/open")
        def open_graph(session: str, request: Request, payload: dict):
            return hub.open(session, payload["graph"], payload["expected_revision"], self.actor(request, "edit"))

        @app.post("/api/agent/sessions/{session}/undo")
        def undo(session: str, request: Request, payload: dict):
            return hub.undo(session, payload["document_id"], payload["expected_revision"], payload.get("redo", False), self.actor(request, "edit"))

        @app.get("/api/agent/sessions/{session}/events")
        def events(session: str, request: Request, after: int = 0):
            self.actor(request, "context")
            return hub.events(session, after)

        @app.get("/api/agent/sessions/{session}/stream")
        async def stream(session: str, request: Request, after: int = 0):
            self.actor(request, "context")
            async def emit():
                cursor = after
                while not await request.is_disconnected():
                    # Revocation also terminates an established event stream.
                    try:
                        self.actor(request, "context")
                    except HTTPException:
                        break
                    result = hub.events(session, cursor)
                    if result["events"] or result["reset"]:
                        yield "data: " + json.dumps(result, ensure_ascii=False) + "\n\n"
                        cursor = result["seq"]
                    else:
                        yield ": heartbeat\n\n"
                    await asyncio.sleep(.35)
            return StreamingResponse(emit(), media_type="text/event-stream")

        @app.get("/api/agent/catalog")
        def catalog(request: Request):
            self.actor(request, "context")
            return service.catalog

        @app.post("/api/agent/validate")
        def validate(request: Request, payload: dict):
            self.actor(request, "context")
            from biopipe.documents import layout
            graph = Graph.model_validate(layout(payload["graph"]))
            result = service.validate_graph(graph, require_files=payload.get("require_files", False))
            return {**result, "graph": graph.model_dump(mode="json")}

        @app.post("/api/agent/sessions/{session}/run")
        def run(session: str, request: Request, payload: dict):
            self.actor(request, "run")
            snapshot = hub.get(session)
            if payload["expected_revision"] != snapshot["revision"]:
                raise CommandError("revision_conflict", "Canvas changed before run", 409)
            doc = next((d for d in snapshot["workspace"]["documents"] if d["id"] == payload["document_id"]), None)
            if doc is None:
                raise CommandError("not_found", "Unknown document", 404)
            return service.launch(Graph.model_validate(doc["graph"]))

        @app.get("/api/agent/jobs/{job}")
        def job(job: str, request: Request):
            self.actor(request, "context")
            return service.details(job)

        @app.post("/api/agent/jobs/{job}/cancel")
        def cancel(job: str, request: Request):
            self.actor(request, "run")
            return service.cancel(job)

        @app.get("/api/agent/plugins")
        def plugins(request: Request):
            self.actor(request, "context")
            return service.plugins.state()

        @app.post("/api/agent/plugins/install")
        def install(request: Request, payload: dict):
            self.actor(request, "plugins")
            try:
                result = service.plugins.install(payload["wheel"])
                service.refresh_catalog()
                return result
            except ValueError as error:
                raise CommandError("plugin_install_failed", str(error)) from error
