import asyncio
import datetime
from typing import Any, Dict, Optional

from fastapi import WebSocket

from api.context import get_thread_context

try:
    import builtins
except ImportError:
    builtins = None


class ToolMonitor:
    """
    Report tool, assistant, and task progress to the active WebSocket thread.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToolMonitor, cls).__new__(cls)
            cls._instance.websocket_manager = None
        return cls._instance

    def set_websocket_manager(self, manager) -> None:
        self.websocket_manager = manager

    def _emit(self, event_type: str, message: Any, data: Optional[Dict[str, Any]] = None) -> None:
        payload = {
            "type": "monitor_event",
            "event": event_type,
            "message": str(message),
            "data": data or {},
            "timestamp": datetime.datetime.now().isoformat(),
        }

        if self.websocket_manager:
            try:
                thread_id = get_thread_context()
                manager_loop = self.websocket_manager.loop
                if thread_id and manager_loop:
                    coroutine = self.websocket_manager.send_to_thread(payload, thread_id)
                    try:
                        current_loop = asyncio.get_running_loop()
                    except RuntimeError:
                        current_loop = None

                    if current_loop and current_loop == manager_loop:
                        current_loop.create_task(coroutine)
                    else:
                        asyncio.run_coroutine_threadsafe(coroutine, manager_loop)
            except Exception as exc:
                print(f"[Monitor] WebSocket send failed: {exc}")

        if builtins and hasattr(builtins, "runtime") and hasattr(builtins.runtime, "stream_writer"):
            try:
                builtins.runtime.stream_writer(payload)
            except Exception:
                pass

        print(f"\n[Monitor:{event_type}] {payload['message']}")

    def report_tool(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> None:
        self._emit("tool_start", f"开始执行工具: {tool_name}", {"tool_name": tool_name, "args": args or {}})

    def report_assistant(self, assistant_name: str, args: Optional[Dict[str, Any]] = None) -> None:
        self._emit("assistant_call", f"正在调用助手: {assistant_name}", {"assistant_name": assistant_name, "args": args or {}})

    def report_task_result(self, result: str) -> None:
        self._emit("task_result", "任务执行完成", {"result": result})

    def report_session_dir(self, path: str) -> None:
        self._emit("session_created", f"工作目录已创建: {path}", {"path": path})

    def report_error(self, message: str) -> None:
        self._emit("error", message)


monitor = ToolMonitor()


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.loop = None

    def set_loop(self, loop) -> None:
        self.loop = loop
        monitor.set_websocket_manager(self)
        print(f"[Monitor] ConnectionManager bound to loop: {id(self.loop)}")

    async def connect(self, websocket: WebSocket, thread_id: str) -> None:
        await websocket.accept()
        self.active_connections[thread_id] = websocket
        print(f"[WebSocket] Client connected: {thread_id}")

    def disconnect(self, websocket: WebSocket, thread_id: str) -> None:
        if self.active_connections.get(thread_id) is websocket:
            self.active_connections.pop(thread_id, None)
        print(f"[WebSocket] Client disconnected: {thread_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        await websocket.send_text(message)

    async def send_to_thread(self, message: dict, thread_id: str) -> None:
        websocket = self.active_connections.get(thread_id)
        if websocket:
            await websocket.send_json(message)


manager = ConnectionManager()
