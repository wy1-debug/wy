import asyncio
import tempfile
import sys
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List, Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import aiofiles


current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from api.monitor import manager  # noqa: E402
from utils.upload_storage import (MAX_UPLOAD_BYTES, MAX_UPLOAD_FILES, SESSION_PATTERN,
                                  available_name, safe_upload_name, session_path)  # noqa: E402


output_dir = project_root / "output"
output_dir.mkdir(exist_ok=True)

updated_dir = project_root / "updated"
updated_dir.mkdir(exist_ok=True)

frontend_dir = project_root / "frontend"
running_tasks: Dict[str, asyncio.Task] = {}
upload_lock = asyncio.Lock()


async def run_deep_agent(query: str, thread_id: str) -> None:
    try:
        from agent.main_agent import run_deep_agent as execute
        await execute(query, thread_id)
    except Exception as exc:
        await manager.send_to_thread({"type": "monitor_event", "event": "error",
                                      "message": f"智能体启动失败: {exc}", "data": {}}, thread_id)


def _resolve_output_path(raw_path: str) -> Path:
    requested = Path(raw_path or "output")
    abs_path = requested.resolve() if requested.is_absolute() else (project_root / requested).resolve()
    output_abs = output_dir.resolve()

    try:
        abs_path.relative_to(output_abs)
    except ValueError:
        raise HTTPException(status_code=403, detail="只能访问 output 目录下的文件")

    return abs_path


def _safe_upload_name(filename: str) -> str:
    try:
        return safe_upload_name(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _track_task(thread_id: str, task: asyncio.Task) -> None:
    running_tasks[thread_id] = task

    def cleanup(done_task: asyncio.Task) -> None:
        if running_tasks.get(thread_id) is done_task:
            running_tasks.pop(thread_id, None)
        try:
            done_task.exception()
        except asyncio.CancelledError:
            pass

    task.add_done_callback(cleanup)


@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    manager.set_loop(loop)
    print(f"[Server] WebSocket manager bound to loop: {id(loop)}")
    yield

    for task in list(running_tasks.values()):
        task.cancel()


app = FastAPI(title="DeepSearch Pro API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")


class TaskRequest(BaseModel):
    query: str
    thread_id: Optional[str] = Field(default=None, pattern=SESSION_PATTERN)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Frontend not found</h1>", status_code=404)


@app.post("/api/task")
async def run_task(request: TaskRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="问题不能为空")

    thread_id = request.thread_id or str(uuid.uuid4())

    old_task = running_tasks.get(thread_id)
    if old_task and not old_task.done():
        old_task.cancel()

    task = asyncio.create_task(run_deep_agent(query, thread_id))
    _track_task(thread_id, task)

    return {"status": "started", "thread_id": thread_id}


@app.post("/api/task/{thread_id}/cancel")
async def cancel_task(thread_id: str):
    task = running_tasks.get(thread_id)
    if not task or task.done():
        return {"status": "not_found", "thread_id": thread_id}

    task.cancel()
    return {"status": "cancelled", "thread_id": thread_id}


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...), thread_id: str = Form(...)):
    try:
        try:
            target_dir = session_path(updated_dir, thread_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if len(files) > MAX_UPLOAD_FILES:
            raise HTTPException(status_code=400, detail=f"每次最多上传 {MAX_UPLOAD_FILES} 个文件")
        names = [_safe_upload_name(file.filename) for file in files]
        task = running_tasks.get(thread_id)
        if task and not task.done():
            raise HTTPException(status_code=409, detail="请等待当前任务完成后再上传")
        with tempfile.TemporaryDirectory(prefix="upload-", dir=updated_dir) as staging:
            for index, file in enumerate(files):
                size = 0
                async with aiofiles.open(Path(staging) / str(index), "wb") as buffer:
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_UPLOAD_BYTES:
                            raise HTTPException(status_code=413, detail=f"{names[index]} 超过 50 MB 限制")
                        await buffer.write(chunk)
                if size == 0:
                    raise HTTPException(status_code=400, detail=f"{names[index]} 是空文件")
            async with upload_lock:
                target_dir.mkdir(parents=True, exist_ok=True)
                saved_files = []
                committed = []
                try:
                    for index, name in enumerate(names):
                        name = available_name(target_dir, name)
                        target = target_dir / name
                        (Path(staging) / str(index)).replace(target)
                        committed.append(target)
                        saved_files.append(name)
                except OSError:
                    for path in committed:
                        path.unlink(missing_ok=True)
                    raise
        return {"status": "uploaded", "files": saved_files}
    except OSError as exc:
        raise HTTPException(status_code=500, detail="文件保存失败，请检查磁盘空间和目录权限") from exc
    finally:
        for file in files:
            await file.close()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/download")
async def download_file(path: str):
    abs_path = _resolve_output_path(path)
    if not abs_path.exists() or not abs_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    return FileResponse(abs_path, filename=abs_path.name)


@app.get("/api/files")
async def list_files(path: str = "output"):
    abs_path = _resolve_output_path(path)
    if not abs_path.exists():
        return {"files": []}
    if not abs_path.is_dir():
        raise HTTPException(status_code=400, detail="path 必须是目录")

    files = []
    for file_path in abs_path.rglob("*"):
        if not file_path.is_file():
            continue
        stat = file_path.stat()
        files.append(
            {
                "name": file_path.name,
                "type": "file",
                "path": str(file_path),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
        )

    files.sort(key=lambda item: item["mtime"], reverse=True)
    return {"files": files}


@app.websocket("/ws/{thread_id}")
async def websocket_endpoint(websocket: WebSocket, thread_id: str):
    await manager.connect(websocket, thread_id)

    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "pong", "message": f"服务端已收到: {data}"})
    except WebSocketDisconnect:
        manager.disconnect(websocket, thread_id)
        print(f"[WebSocket] 客户端已断开: {thread_id}")
    except Exception as exc:
        print(f"[WebSocket] 连接异常: {exc}")
        manager.disconnect(websocket, thread_id)


if __name__ == "__main__":
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)
