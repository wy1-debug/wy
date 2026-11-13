import os
from pathlib import Path
from typing import Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
VIRTUAL_PREFIXES = ("/workspace", "/mnt/data", "/home/user")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _strip_virtual_prefix(raw_path: str) -> str:
    normalized = raw_path.replace("\\", "/").strip()
    for prefix in VIRTUAL_PREFIXES:
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return normalized[len(prefix):].lstrip("/")
    return normalized


def _strip_known_session_prefix(parts: tuple[str, ...], session_name: str) -> tuple[str, ...]:
    if not parts:
        return parts

    cleaned = tuple(part for part in parts if part not in ("", "."))

    if session_name in cleaned:
        return cleaned[cleaned.index(session_name) + 1:]

    if cleaned and cleaned[0] in {"output", "updated"}:
        cleaned = cleaned[1:]
        if cleaned and cleaned[0] == session_name:
            cleaned = cleaned[1:]

    return cleaned


def resolve_path(filename: str, session_dir: Optional[str] = None) -> str:
    """
    Resolve a model/user supplied file path.

    When a session directory is provided, all returned paths are constrained to
    that directory. This keeps generated and uploaded-file reads isolated per
    task while still accepting common model-produced paths such as
    "output/session_x/report.md", "session_x/report.md", or "/workspace/file.md".
    """
    if not filename or not str(filename).strip():
        raise ValueError("文件名不能为空")

    raw_path = _strip_virtual_prefix(str(filename))
    path = Path(raw_path)

    if not session_dir:
        return str(path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve())

    session_path = Path(session_dir).resolve()
    session_name = session_path.name

    is_unix_style_absolute = raw_path.startswith("/") and not path.drive
    if path.is_absolute() and not (os.name == "nt" and is_unix_style_absolute):
        resolved = path.resolve()
        if not _is_relative_to(resolved, session_path):
            raise ValueError(f"路径不在当前会话目录内: {filename}")

        relative_parts = resolved.relative_to(session_path).parts
        if relative_parts and relative_parts[0] == session_name:
            resolved = (session_path / Path(*relative_parts[1:])).resolve()
        return str(resolved)

    relative_raw = raw_path.lstrip("/") if is_unix_style_absolute else raw_path
    relative_parts = _strip_known_session_prefix(Path(relative_raw).parts, session_name)
    target = session_path.joinpath(*relative_parts).resolve() if relative_parts else session_path

    if not _is_relative_to(target, session_path):
        raise ValueError(f"路径不在当前会话目录内: {filename}")

    return str(target)
