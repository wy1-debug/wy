import logging
from pathlib import Path
from typing import Annotated, Optional

from langchain_core.tools import tool

from api.context import get_session_context
from api.monitor import monitor
from utils.path_utils import resolve_path
from utils.word_converter import convert_md_to_pdf_via_word


@tool
def convert_md_to_pdf(
    md_filename: Annotated[str, "要转换的 Markdown 文件名或相对路径，支持带或不带 .md 后缀"],
    pdf_filename: Annotated[Optional[str], "输出 PDF 文件名或相对路径，默认与源文件同名"] = None,
) -> str:
    """
    将当前会话工作目录中的 Markdown 文档转换为 PDF。
    Windows 环境下优先使用 Microsoft Word COM 引擎完成转换。
    """
    monitor.report_tool("Markdown 转 PDF 工具", {"md_filename": md_filename, "pdf_filename": pdf_filename})

    try:
        session_dir = get_session_context()
        md_path = Path(resolve_path(str(Path(md_filename).with_suffix(".md")), session_dir))
        if not md_path.exists():
            return f"Markdown 文件不存在: {md_path.name}"

        if pdf_filename:
            pdf_path = Path(resolve_path(str(Path(pdf_filename).with_suffix(".pdf")), session_dir))
        else:
            pdf_path = md_path.with_suffix(".pdf")

        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        return convert_md_to_pdf_via_word(md_path, pdf_path)
    except Exception as exc:
        logging.error("Markdown 转 PDF 失败: %s", exc, exc_info=True)
        return f"Markdown 转 PDF 失败: {exc}"
