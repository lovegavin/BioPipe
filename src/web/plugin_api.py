"""Local, token-protected plugin management; installations run off the UI loop."""
import asyncio
from pathlib import Path
import shutil
import uuid

from fastapi import HTTPException, Request


def mount_plugins(app, service):
    operations = {}
    active = set()

    def public_state():
        state = service.plugins.state()
        from biopipe.packages import bundled_state
        result = {key: state[key] for key in ("generation", "packages", "descriptors")}
        result["bundled_packages"] = bundled_state()["packages"]
        return result

    def check_idle():
        if active:
            raise HTTPException(409, "另一个插件操作正在进行，请等待完成。")

    async def execute(key, wheel=None, remove=None, temporary=None, name=None, action=None):
        try:
            if action:
                await asyncio.to_thread(service.plugins.manage, name, action)
            else:
                await asyncio.to_thread(service.plugins.install, wheel, remove=remove)
            service.refresh_catalog()
            operations[key].update(status="complete")
        except Exception as exc:
            operations[key].update(status="failed", error=str(exc))
        finally:
            active.discard(key)
            if temporary:
                shutil.rmtree(temporary)

    def start(key, **kwargs):
        operations[key] = {"id": key, "status": "running", "error": None}
        task = asyncio.create_task(execute(key, **kwargs))
        # Keep tasks alive until their transactional install finishes.
        app.state.plugin_tasks.add(task)
        task.add_done_callback(app.state.plugin_tasks.discard)
        return operations[key]

    app.state.plugin_tasks = set()

    @app.get("/api/plugins")
    def plugins():
        return public_state()

    @app.get("/api/plugins/operations/{key}")
    def operation(key: str):
        if key not in operations:
            raise HTTPException(404, "插件操作不存在。")
        return operations[key]

    @app.post("/api/plugins/install")
    async def install(request: Request, filename: str):
        check_idle()
        if (Path(filename).name != filename or any(c in filename for c in '\\/:*?"<>|')
                or not filename.endswith(".whl")):
            raise HTTPException(422, "请选择有效的 .whl 插件包。")
        key = uuid.uuid4().hex
        active.add(key)
        temporary = service.plugins.directory / "incoming" / key
        try:
            temporary.mkdir(parents=True)
            target = temporary / filename
            size = 0
            with target.open("wb") as output:
                async for chunk in request.stream():
                    size += len(chunk)
                    if service.settings.max_upload is not None and size > service.settings.max_upload:
                        raise HTTPException(413, "插件包超过已配置的上传上限。")
                    output.write(chunk)
            if not size:
                raise HTTPException(422, "插件包为空。")
            return start(key, wheel=target, temporary=temporary)
        except BaseException:
            active.discard(key)
            if temporary.exists():
                shutil.rmtree(temporary)
            raise

    @app.post("/api/plugins/remove")
    async def remove(payload: dict):
        check_idle()
        name = payload.get("name")
        if name not in {p["name"] for p in service.plugins.state()["packages"]}:
            raise HTTPException(422, "该插件未安装。")
        key = uuid.uuid4().hex
        active.add(key)
        return start(key, remove=name)

    @app.post("/api/plugins/manage")
    async def manage(payload: dict):
        check_idle()
        if payload.get("action") not in {"enable", "disable", "restore"} or not isinstance(payload.get("name"), str):
            raise HTTPException(422, "请选择有效的包与操作。")
        key = uuid.uuid4().hex
        active.add(key)
        return start(key, name=payload["name"], action=payload["action"])
