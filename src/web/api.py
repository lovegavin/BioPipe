import asyncio
from contextlib import asynccontextmanager
import hmac
import json
import logging
import os
from pathlib import Path
from typing import Literal
import secrets
from urllib.parse import urlparse
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
import yaml

from src.core import ManifestError
from biopipe import __version__
from .operator_catalog import catalog_from_descriptors
from src.task.memory.config import AUTO_BUDGET_FRACTION
from .graph import GraphError, compile_graph, import_manifest, project_path, relative_manifest
from .models import Graph, ManifestImport, SaveWorkflow, RegisterRoutes, Workspace, LibraryAction
from .routes import prepare_interface
from .parameters import freeze_graph, export_bundle, import_bundle
from .contracts import analyze_graph
from .service import JobService, Settings, read_json, safe_json
from .assets import AssetImports, accepted_extensions


def create_app(settings=None):
    root = Path(__file__).resolve().parents[2]
    if settings is None:
        from .profile import make_settings
        settings = make_settings(root, root / "frontend/dist")
    catalog = catalog_from_descriptors()
    service = JobService(settings, catalog)
    catalog = service.catalog
    imports = AssetImports(service)
    token = secrets.token_urlsafe(32)
    # Admission owns the one host snapshot. UI and workers use that same value.
    automatic_memory_budget = service.admission.capacity or None
    @asynccontextmanager
    async def lifespan(app):
        bridge.publish(getattr(app.state, "instance_url", None) or settings.instance_url)
        if not settings.testing:
            from biopipe.runtime import remember_runtime
            remember_runtime()
            app.state.check_dependencies()
        yield
        bridge.close()
        executions.shutdown()
        service.shutdown()
    app = FastAPI(title="BioPipe Studio", version=__version__, lifespan=lifespan)
    app.state.service, app.state.token = service, token
    from biopipe.bridge import Bridge
    bridge = Bridge(app, service, token)
    app.state.bridge = bridge
    from .plugin_api import mount_plugins
    mount_plugins(app, service)
    from .remote_api import mount_remote
    remote_events, remote_console = mount_remote(app, service)
    from .execution import ExecutionService
    executions = ExecutionService(service)
    app.state.executions = service.executions = executions
    from .execution_api import mount_execution, ACTIVE_STATUSES
    execution_events, execution_console = mount_execution(app, service, executions)

    def graph_catalog(graph):
        return executions.catalog(graph) if executions.applies(graph) else service.graph_catalog(graph)

    def prepare(graph):
        return executions.prepare(graph) if executions.applies(graph) else service.prepare_graph(graph)

    service.routes.catalog_for = graph_catalog

    @app.middleware("http")
    async def local_boundary(request, call_next):
        request_id = uuid.uuid4().hex[:12]
        host = request.url.hostname
        origin = request.headers.get("origin")
        if not settings.testing and (host not in ("localhost", "127.0.0.1") or
                                    (origin and urlparse(origin).hostname not in ("localhost", "127.0.0.1"))):
            return JSONResponse({"message": "此服务仅允许本地访问。"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS") and not request.url.path.startswith("/api/agent/"):
            if not hmac.compare_digest(request.headers.get("x-studio-token", ""), token):
                return JSONResponse({"message": "本地会话已更新，请刷新页面。"}, status_code=403)
        try:
            if service.refresh_catalog() and not settings.testing:
                app.state.check_dependencies_if_idle()
            response = await call_next(request)
        except Exception:
            logging.exception("studio request failure", extra={"request_id": request_id})
            response = JSONResponse({"message": "本地服务处理失败，请检查服务日志。", "request_id": request_id}, status_code=500)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Cache-Control"] = "no-store" if request.url.path.startswith("/api") else "no-cache"
        return response

    @app.exception_handler(GraphError)
    async def graph_error(request, exc):
        return JSONResponse({"message": str(exc), "node_id": exc.node_id}, status_code=422)

    @app.exception_handler(ManifestError)
    async def manifest_error(request, exc):
        return JSONResponse({"message": str(exc)}, status_code=422)

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"message": str(exc).strip("'")}, status_code=404)

    @app.exception_handler(ValueError)
    async def invalid_value(request, exc):
        return JSONResponse({"code": "invalid_request", "message": str(exc)}, status_code=422)

    @app.get("/health")
    @app.get("/ready")
    def health():
        return {"status": "ok", "studio": __version__}

    @app.get("/api/bootstrap")
    def bootstrap():
        import sys
        agent_args = ["-m", "biopipe", "--workspace", str(service.root), "--data-dir", str(service.directory), "mcp"]
        return {"token": token, "catalog": catalog, "demo": service.demo,
                "automatic_memory_fraction": AUTO_BUDGET_FRACTION,
                "automatic_memory_budget_bytes": automatic_memory_budget,
                "agent_config": {"command": sys.executable, "args": agent_args},
                "history": history(),
                "upload_limit_mb": settings.max_upload / 1024**2 if settings.max_upload is not None else None,
                "upload_extensions": accepted_extensions(catalog),
                "storage": settings.profile or {"workspace": str(service.root), "data_dir": str(service.directory),
                                                "registry": str(service.routes.directory / "registry.json")},
                "desktop": settings.desktop}

    @app.get("/api/workspace")
    def workspace():
        return service.routes.load_workspace()

    @app.post("/api/workspace")
    def save_workspace(workspace: Workspace):
        service.routes.save_workspace(workspace)
        return {"saved": True}

    @app.get("/api/workflows")
    def saved_workflows():
        return service.routes.list_saved()

    @app.post("/api/workflows/prepare")
    def prepare_workflow(graph: Graph):
        return prepare(graph).model_dump(mode="json")

    @app.post("/api/workflows/export")
    def export_workflow(graph: Graph):
        prepared = Graph.model_validate(prepare_workflow(graph))
        return Response(export_bundle(prepared), media_type="application/zip")

    @app.post("/api/workflows/import")
    async def import_workflow(request: Request):
        try:
            return import_bundle(await request.body()).model_dump(mode="json")
        except ValueError as exc:
            raise GraphError(str(exc)) from exc

    @app.post("/api/workflows/save")
    def save_workflow(payload: SaveWorkflow):
        payload.graph = prepare(payload.graph)
        return service.routes.save(payload)

    @app.get("/api/workflows/{key}")
    def get_workflow(key: str):
        return service.routes.get(key)

    @app.get("/api/routes")
    def routes():
        return service.routes.routes()

    @app.post("/api/routes/register")
    def register_routes(payload: RegisterRoutes):
        return service.routes.register(payload.workflow_ids)

    @app.get("/api/library/state")
    def library_state():
        return service.routes.library_state()

    @app.post("/api/library/manage")
    def manage_library(payload: LibraryAction):
        return service.routes.manage_item(payload.key, payload.action)

    @app.get("/api/operators")
    def operators():
        return catalog

    @app.post("/api/validate")
    def validate(graph: Graph):
        return executions.validate(graph) if executions.applies(graph) else service.validate_graph(graph)

    @app.post("/api/contracts")
    def contracts(graph: Graph):
        return analyze_graph(graph, graph_catalog(graph), settings.root)

    @app.post("/api/export")
    def export(graph: Graph):
        from .source_paths import remote_profile
        if executions.applies(graph):
            raise GraphError('多环境工作流请导出路线包。')
        if remote_profile(graph):
            return service.remotes.call(remote_profile(graph), 'export', {'graph': graph.model_dump(mode='json')})
        manifest, order = compile_graph(graph, service.plugins.catalog_for(graph, service.base_catalog), settings.root)
        manifest = relative_manifest(manifest, project_path(settings.root, ".", graph.base_dir), service.plugins.catalog_for(graph, service.base_catalog))
        return {"yaml": yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), "order": order}

    @app.post("/api/import")
    def import_yaml(payload: ManifestImport):
        try:
            return import_manifest(payload.text, payload.base_dir, catalog, settings.root).model_dump(mode="json")
        except yaml.YAMLError as exc:
            raise GraphError("YAML 格式有误，请检查缩进及字段。") from exc

    @app.post("/api/assets/batches")
    async def begin_upload(request: Request):
        payload = await request.json()
        return imports.create(payload.get('filenames') if isinstance(payload, dict) else None)

    @app.post("/api/assets/batches/{key}/complete")
    async def complete_upload(key: str, request: Request):
        payload = await request.json()
        return imports.complete(key, payload.get('base_dir', '.'))

    @app.post("/api/assets/batches/{key}/cancel")
    def cancel_upload(key: str):
        imports.cancel(key)
        return {'cancelled': True}

    @app.post("/api/assets")
    async def upload(request: Request, filename: str = "data.csv", batch: str | None = None):
        single = batch is None
        if single:
            batch = imports.create([filename])['id']
        path = imports.target(batch, filename)
        temporary = path.with_name('.' + path.name + '.part')
        total = 0
        owns_temporary = False
        try:
            with open(temporary, "xb") as file:
                owns_temporary = True
                async for block in request.stream():
                    total += len(block)
                    if settings.max_upload is not None and total > settings.max_upload:
                        raise HTTPException(413, "文件超过本地上传上限。")
                    file.write(block)
            if not total:
                raise GraphError("上传的文件为空。")
            temporary.replace(path)
            if single:
                imports.complete(batch)
        except BaseException as exc:
            if owns_temporary:
                temporary.unlink(missing_ok=True)
            if single:
                imports.cancel(batch)
            if isinstance(exc, FileExistsError):
                raise GraphError('文件正在上传，请勿重复提交。') from exc
            raise
        return {"path": str(path.relative_to(settings.root)).replace("\\", "/"), "filename": filename, "bytes": total}

    @app.get("/api/jobs")
    def history():
        parents = executions.history()
        child_ids = set()
        for parent in parents:
            for child in parent.get('children', []):
                if not isinstance(child, dict):
                    continue
                key = child.get('id') or child.get('job_id')
                if not key:
                    continue
                location = child.get('target') or {}
                profile = location.get('profile_id') if location.get('kind') == 'ssh' else None
                if profile:
                    # Older cached remote summaries omitted parent lineage and
                    # wrap their server ID when reconnecting to the editor.
                    prefix = f'ssh-{profile}-'
                    child_ids.add(key if key.startswith(prefix) else prefix + key)
                else:
                    child_ids.add(key)
        local = [job for job in service.history()
                 if not job.get('execution_parent_id') and job['id'] not in child_ids]
        return sorted(local + parents, key=lambda job: job['created_at'], reverse=True)[:60]

    @app.post("/api/jobs", status_code=202)
    def run_job(graph: Graph):
        return executions.launch(graph) if executions.applies(graph) else service.launch(graph)

    @app.get("/api/jobs/{key}")
    def details(key: str):
        return executions.details(key) if executions.owns(key) else service.details(key)

    @app.post("/api/jobs/{key}/cancel")
    def cancel(key: str):
        return executions.cancel(key) if executions.owns(key) else service.cancel(key)

    @app.get("/api/jobs/{key}/events")
    async def events(key: str, request: Request):
        if executions.owns(key):
            return await execution_events(key, request)
        if service.remotes.owns(key):
            return await remote_events(key, request)
        service.require(key)
        async def stream():
            offsets = {}
            console_signature = None
            sequence = 0
            while not await request.is_disconnected():
                # Read completion first: a terminal snapshot guarantees all logs
                # were flushed. Reading it after the files can lose their last rows.
                job = service.details(key)
                terminal = job["status"] not in ACTIVE_STATUSES and job.get("logs_complete", True)
                batch, eof = [], True
                for path in service.event_paths(key):
                    with open(path, encoding="utf-8") as file:
                        file.seek(offsets.get(path, 0))
                        for _ in range(200):
                            previous = file.tell()
                            line = file.readline()
                            if not line or (not terminal and not line.endswith("\n")):
                                offsets[path] = previous
                                break
                            offsets[path] = file.tell()
                            try:
                                batch.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                        else:
                            eof = False
                batch.sort(key=lambda event: event.get("time", ""))
                console_signature, console = service.console_snapshot(key, job, console_signature)
                # The graph is fetched once at launch/restore, not retransmitted
                # every 400 ms for a large DAG.
                job.pop("graph", None)
                done = terminal and eof
                sequence += 1
                payload = safe_json({"job": job, "events": batch, "done": done, **(console or {})})
                yield f"id: {sequence}\nevent: update\ndata: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n"
                if done:
                    break
                await asyncio.sleep(.4)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

    def result_service(key):
        if executions.owns(key):
            return executions
        if service.remotes.owns(key):
            return service.remotes
        return service

    @app.get("/api/jobs/{key}/artifacts/{artifact_id}/preview")
    def preview(key: str, artifact_id: str):
        return result_service(key).preview(key, artifact_id)

    @app.get("/api/jobs/{key}/artifacts/{artifact_id}/download")
    def download(key: str, artifact_id: str):
        path, descriptor = result_service(key).artifact(key, artifact_id)
        suffix = ".files.json" if descriptor.get("kind") == "file" else ".npy"
        return FileResponse(path, filename=descriptor["name"] + suffix, media_type="application/octet-stream")

    @app.get("/api/jobs/{key}/artifacts/{artifact_id}/files/{role}")
    def artifact_file(key: str, artifact_id: str, role: str):
        path = result_service(key).artifact_file(key, artifact_id, role)
        return FileResponse(path, filename=path.name, media_type="application/octet-stream")

    @app.get("/api/jobs/{key}/exports/{index}")
    def step_export(key: str, index: int):
        path = result_service(key).export_file(key, index)
        if path.stat().st_size > 4 * 1024**2:
            return {"message": "步骤报告较大，请下载查看。"}
        return safe_json(read_json(path))

    @app.get("/api/jobs/{key}/exports/{index}/download")
    def export_download(key: str, index: int):
        path = result_service(key).export_file(key, index)
        return FileResponse(path, filename=path.name, media_type="application/json")

    @app.get("/api/jobs/{key}/exports/{index}/figure")
    def figure(key: str, index: int, format: Literal["png", "pdf", "svg", "jpg", "jpeg", "webp", "tif", "tiff"] | None = None, figure_id: str | None = None):
        path = result_service(key).figure_file(key, index, format=format, **({"figure_id": figure_id} if figure_id is not None else {}))
        return FileResponse(path, filename=path.name, content_disposition_type="inline")

    @app.get("/api/jobs/{key}/console")
    def console(key: str):
        if executions.owns(key):
            return execution_console(key)
        if service.remotes.owns(key):
            return remote_console(key)
        job = service.require(key)
        path = service.jobs_dir / key / "console.log"
        if not path.is_file() or path.stat().st_size == 0:
            _, snapshot = service.console_snapshot(key, job)
            return PlainTextResponse(snapshot["console"])
        return FileResponse(path, media_type="text/plain", filename="console.log")

    if settings.dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.dist_dir, html=True), name="studio")
    return app
