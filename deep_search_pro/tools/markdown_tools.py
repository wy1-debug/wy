from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from api.context import get_session_context
from api.monitor import monitor
from utils.path_utils import resolve_path


@tool
def generate_markdown(
    content: Annotated[str, "要写入 Markdown 文档的完整文本内容"],
    filename: Annotated[str, "Markdown 文件名，可以包含或不包含 .md 后缀"],
    path: Annotated[str, "可选的相对保存目录，默认保存在当前会话工作目录"] = "",
) -> str:
    """
    根据提供的文本内容生成 Markdown(.md) 文件。
    文件必须保存在当前会话工作目录内；path 和 filename 都应使用相对路径。
    """
    monitor.report_tool("Markdown 文档生成工具", {"filename": filename, "path": path})

    if not filename.lower().endswith(".md"):
        filename += ".md"

    try:
        input_path = str(Path(path) / filename) if path and path != "." else filename
        file_path = Path(resolve_path(input_path, get_session_context()))
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"Markdown 文件已生成: {file_path.name}"
    except Exception as exc:
        return f"生成 Markdown 文件失败: {exc}"
