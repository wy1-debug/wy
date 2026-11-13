"""Validated upload storage shared by the API and agent."""
import re
from pathlib import Path

SESSION_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$"
SUPPORTED_EXTENSIONS = {".md", ".txt", ".csv", ".json", ".yml", ".yaml", ".docx", ".pdf", ".xlsx", ".xls"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_UPLOAD_FILES = 20


def session_path(root: Path, session_id: str) -> Path:
    if not re.fullmatch(SESSION_PATTERN, session_id):
        raise ValueError("会话 ID 只能包含字母、数字、下划线和连字符，长度为 1–128")
    target = (root / f"session_{session_id}").resolve()
    target.relative_to(root.resolve())
    return target


def safe_upload_name(filename: str) -> str:
    name = Path((filename or "").replace("\\", "/")).name
    if not name or name in {".", ".."} or len(name) > 200:
        raise ValueError("文件名无效或过长")
    if any(ord(char) < 32 or char in '<>:"|?*' for char in name) or name.endswith((" ", ".")):
        raise ValueError("文件名包含不支持的字符")
    if name.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        raise ValueError("文件名为系统保留名称")
    if Path(name).suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError("不支持此文件类型，请上传 txt、md、csv、json、yaml、docx、pdf、xlsx 或 xls")
    return name


def available_name(directory: Path, name: str) -> str:
    existing = {path.name.casefold() for path in directory.iterdir()}
    candidate = name
    counter = 1
    path = Path(name)
    while candidate.casefold() in existing:
        candidate = f"{path.stem} ({counter}){path.suffix}"
        counter += 1
    return candidate
