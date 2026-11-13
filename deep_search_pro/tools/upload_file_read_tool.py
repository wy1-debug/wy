from pathlib import Path
from typing import Annotated

from langchain_core.tools import tool

from api.context import get_session_context
from api.monitor import monitor
from utils.path_utils import resolve_path

try:
    import docx
except ImportError:
    docx = None

try:
    import pypdf
except ImportError:
    pypdf = None

try:
    import pandas as pd
except ImportError:
    pd = None


def _read_text_file(file_path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return file_path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return file_path.read_text(encoding="utf-8", errors="replace")


@tool
def read_file_content(
    filename: Annotated[str, "要读取的文件名或相对路径，支持 .md/.txt/.docx/.pdf/.xlsx/.xls"],
    instruction: Annotated[str, "读取目的，例如: 提取摘要、统计数据、提取全部内容"] = "提取全部内容",
) -> str:
    """
    读取当前会话工作目录中的上传文件或生成文件。
    支持 Markdown、文本、Word、PDF 和 Excel；Excel 会返回预览、列名和统计信息。
    """
    monitor.report_tool("文件内容读取工具", {"filename": filename, "instruction": instruction})

    try:
        session_dir = get_session_context()
        file_path = Path(resolve_path(filename, session_dir))
    except Exception as exc:
        return f"文件路径无效: {exc}"

    if not file_path.exists() or not file_path.is_file():
        return f"文件不存在: {filename} (解析路径: {file_path})"

    ext = file_path.suffix.lower()

    try:
        if ext in {".md", ".txt", ".csv", ".json", ".yml", ".yaml"}:
            return _read_text_file(file_path)

        if ext == ".docx":
            if docx is None:
                return "缺少 python-docx，无法读取 Word 文件。"
            document = docx.Document(str(file_path))
            paragraphs = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
            table_lines = []
            for table in document.tables:
                for row in table.rows:
                    table_lines.append(" | ".join(cell.text for cell in row.cells))
            return "\n".join(paragraphs + table_lines)

        if ext == ".pdf":
            if pypdf is None:
                return "缺少 pypdf，无法读取 PDF 文件。"
            reader = pypdf.PdfReader(str(file_path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages).strip() or "PDF 未提取到文本，可能是扫描件，请先进行 OCR 或上传可复制文本的 PDF。"

        if ext in {".xlsx", ".xls"}:
            if pd is None:
                return "缺少 pandas/openpyxl，无法读取 Excel 文件。"
            sheets = pd.read_excel(str(file_path), sheet_name=None)
            sections = []
            for sheet_name, dataframe in sheets.items():
                lines = [
                    f"文件: {file_path.name}",
                    f"工作表: {sheet_name}",
                    f"行数: {len(dataframe)}, 列数: {len(dataframe.columns)}",
                    f"列名: {', '.join(dataframe.columns.astype(str))}",
                    "",
                    "[前 10 行预览]",
                    dataframe.head(10).to_string(index=False),
                ]
                numeric = dataframe.select_dtypes(include="number")
                if not numeric.empty:
                    lines.extend(["", "[数值列统计]", numeric.describe().to_string()])
                sections.append("\n".join(lines))
            return "\n\n".join(sections)

        return _read_text_file(file_path)
    except Exception as exc:
        return f"读取文件失败: {exc}"
