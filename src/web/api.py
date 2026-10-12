import asyncio
from contextlib import asynccontextmanager
import hmac
import json
import logging
import os
from pathlib import Path
import secrets
from urllib.parse import urlparse
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import yaml

from src.core import ManifestError
from src.task import STEPS
from src.task.operator_catalog import build_catalog
from .graph import GraphError, compile_graph, import_manifest, project_path, relative_manifest
from .models import Graph, ManifestImport
from .contracts import analyze_graph
from .service import JobService, Settings, read_json, safe_json


def create_app(settings=None):
    root = Path(__file__).resolve().parents[2]
    settings = settings or Settings(root, root / os.getenv("BIOPIPE_STUDIO_DATA", ".local/studio"), root / "frontend/dist")
    catalog = build_catalog(STEPS)
    service = JobService(settings, catalog)
    token = secrets.token_urlsafe(32)
    @asynccontextmanager
    async def lifespan(app):
        yield
        service.shutdown()
    app = FastAPI(title="BioPipe Studio", version="0.1.0", lifespan=lifespan)
    app.state.service, app.state.token = service, token

    @app.middleware("http")
    async def local_boundary(request, call_next):
        request_id = uuid.uuid4().hex[:12]
        host = request.url.hostname
        origin = request.headers.get("origin")
        if not settings.testing and (host not in ("localhost", "127.0.0.1") or
                                    (origin and urlparse(origin).hostname not in ("localhost", "127.0.0.1"))):
            return JSONResponse({"message": "此服务仅允许本地访问。"}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not hmac.compare_digest(request.headers.get("x-studio-token", ""), token):
                return JSONResponse({"message": "本地会话已更新，请刷新页面。"}, status_code=403)
        if request.url.path.startswith("/api") and not request.url.path.startswith("/api/assets"):
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"message": "请求长度无效。"}, status_code=400)
            if length > 2 * 1024**2:
                return JSONResponse({"message": "工作流配置超过 2 MiB，请缩小配置。"}, status_code=413)
        try:
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

    @app.get("/health")
    @app.get("/ready")
    def health():
        return {"status": "ok", "studio": "0.1.0"}

    @app.get("/api/bootstrap")
    def bootstrap():
        return {"token": token, "catalog": catalog, "demo": service.demo,
                "history": service.history(), "upload_limit_mb": settings.max_upload // 1024**2,
                "desktop": settings.desktop, "draft": service.load_draft() if settings.desktop else None}

    @app.post("/api/draft")
    def save_draft(graph: Graph):
        if not settings.desktop:
            raise HTTPException(404, "Desktop draft storage is not enabled")
        service.save_draft(graph)
        return {"saved": True}

    @app.get("/api/operators")
    def operators():
        return catalog

    @app.post("/api/validate")
    def validate(graph: Graph):
        manifest, order = compile_graph(graph, catalog, settings.root, require_files=True)
        return {"valid": True, "order": order, "manifest": manifest,
                "contracts": analyze_graph(graph, catalog, settings.root)}

    @app.post("/api/contracts")
    def contracts(graph: Graph):
        return analyze_graph(graph, catalog, settings.root)

    @app.post("/api/export")
    def export(graph: Graph):
        manifest, order = compile_graph(graph, catalog, settings.root)
        manifest = relative_manifest(manifest, project_path(settings.root, ".", graph.base_dir))
        return {"yaml": yaml.safe_dump(manifest, allow_unicode=True, sort_keys=False), "order": order}

    @app.post("/api/import")
    def import_yaml(payload: ManifestImport):
        try:
            return import_manifest(payload.text, payload.base_dir, catalog, settings.root).model_dump(mode="json")
        except yaml.YAMLError as exc:
            raise GraphError("YAML 格式有误，请检查缩进及字段。") from exc

    @app.post("/api/assets")
    async def upload(request: Request, filename: str = "data.csv"):
        filename = Path(filename).name
        if not filename.lower().endswith((".csv", ".csv.gz")) or any(c in filename for c in "\\/:"):
            raise GraphError("首版上传支持 CSV 或 CSV.gz；其他格式可使用项目内文件路径。")
        suffix = ".csv.gz" if filename.lower().endswith(".csv.gz") else ".csv"
        path = service.assets_dir / (uuid.uuid4().hex + suffix)
        total = 0
        try:
            with open(path, "xb") as file:
                async for block in request.stream():
                    total += len(block)
                    if total > settings.max_upload:
                        raise HTTPException(413, "文件超过本地上传上限。")
                    file.write(block)
            if not total:
                raise GraphError("上传的文件为空。")
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return {"path": str(path.relative_to(settings.root)).replace("\\", "/"), "filename": filename, "bytes": total}

    @app.get("/api/jobs")
    def history():
        return service.history()

    @app.post("/api/jobs", status_code=202)
    def run_job(graph: Graph):
        return service.launch(graph)

    @app.get("/api/jobs/{key}")
    def details(key: str):
        return service.details(key)

    @app.post("/api/jobs/{key}/cancel")
    def cancel(key: str):
        return service.cancel(key)

    @app.get("/api/jobs/{key}/events")
    async def events(key: str, request: Request):
        service.require(key)
        async def stream():
            offset = 0
            sequence = 0
            while not await request.is_disconnected():
                path = service.events_path(key)
                batch, eof = [], True
                if path:
                    with open(path, encoding="utf-8") as file:
                        file.seek(offset)
                        for _ in range(200):
                            previous = file.tell()
                            line = file.readline()
                            if not line or not line.endswith("\n"):
                                offset = previous
                                break
                            offset = file.tell()
                            try:
                                batch.append(json.loads(line))
                            except json.JSONDecodeError:
                                continue
                        else:
                            eof = False
                job = service.details(key)
                # The graph is fetched once at launch/restore, not retransmitted
                # every 400 ms for a large DAG.
                job.pop("graph", None)
                done = job["status"] != "running" and eof
                sequence += 1
                payload = safe_json({"job": job, "events": batch, "done": done})
                yield f"id: {sequence}\nevent: update\ndata: {json.dumps(payload, ensure_ascii=False, allow_nan=False)}\n\n"
                if done:
                    break
                await asyncio.sleep(.4)
        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})

    @app.get("/api/jobs/{key}/artifacts/{artifact_id}/preview")
    def preview(key: str, artifact_id: str):
        return service.preview(key, artifact_id)

    @app.get("/api/jobs/{key}/artifacts/{artifact_id}/download")
    def download(key: str, artifact_id: str):
        path, descriptor = service.artifact(key, artifact_id)
        return FileResponse(path, filename=descriptor["name"] + ".npy", media_type="application/octet-stream")

    @app.get("/api/jobs/{key}/exports/{index}")
    def step_export(key: str, index: int):
        path = service.export_file(key, index)
        if path.stat().st_size > 4 * 1024**2:
            return {"message": "步骤报告较大，请下载查看。"}
        return safe_json(read_json(path))

    @app.get("/api/jobs/{key}/exports/{index}/download")
    def export_download(key: str, index: int):
        path = service.export_file(key, index)
        return FileResponse(path, filename=path.name, media_type="application/json")

    @app.get("/api/jobs/{key}/exports/{index}/figure")
    def figure(key: str, index: int):
        return FileResponse(service.figure_file(key, index))

    @app.get("/api/jobs/{key}/console")
    def console(key: str):
        service.require(key)
        path = service.jobs_dir / key / "console.log"
        return FileResponse(path, media_type="text/plain", filename="console.log")

    if settings.dist_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.dist_dir, html=True), name="studio")
    return app
