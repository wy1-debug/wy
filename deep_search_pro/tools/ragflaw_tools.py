from typing import Annotated, Any, Optional

from langchain_core.tools import tool

from api.monitor import monitor
from rawflow.rag_config import _load_ragflow_env

try:
    from ragflow_sdk import RAGFlow
except ImportError:
    RAGFlow = None


_ragflow_client = None


def _get_ragflow_client():
    global _ragflow_client
    if _ragflow_client is not None:
        return _ragflow_client

    if RAGFlow is None:
        raise RuntimeError("未安装 ragflow-sdk，无法使用 RAGFlow 工具")

    api_key, base_url = _load_ragflow_env()
    if not api_key or not base_url:
        raise RuntimeError("缺少 RAGFLOW_API_KEY 或 RAGFLOW_API_URL 配置")

    _ragflow_client = RAGFlow(api_key=api_key, base_url=base_url)
    return _ragflow_client


def _get_attr(obj: Any, name: str, default: Any = "") -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _format_dataset_names(datasets: Optional[list[Any]]) -> str:
    if not datasets:
        return "无"

    names = []
    for dataset in datasets:
        name = _get_attr(dataset, "name", None) or _get_attr(dataset, "id", None)
        if name:
            names.append(str(name))
    return "、".join(names) if names else "无"


@tool
def get_assistant_list() -> str:
    """
    查询 RAGFlow 服务中可用的聊天助手及其关联知识库。
    调用 create_ask_delete 之前应先调用本工具确认助手名称。
    """
    monitor.report_tool("RAGFlow 助手列表查询工具")

    try:
        client = _get_ragflow_client()
        chats = client.list_chats()
        if not chats:
            return "当前 RAGFlow 服务没有可用助手。"

        lines = []
        for chat in chats:
            name = _get_attr(chat, "name", "未命名助手")
            description = _get_attr(chat, "description", "")
            datasets = _format_dataset_names(_get_attr(chat, "datasets", []) or [])
            lines.append(f"助手名称: {name}\n功能介绍: {description}\n关联知识库: {datasets}")

        return "\n\n".join(lines)
    except Exception as exc:
        return f"查询 RAGFlow 助手列表失败: {exc}"


@tool
def create_ask_delete(
    chat_name: Annotated[str, "RAGFlow 助手名称，必须来自 get_assistant_list 的返回结果"],
    question: Annotated[str, "要向该 RAGFlow 助手提出的问题"],
) -> str:
    """
    向指定 RAGFlow 助手提问，创建临时会话、获取回答后删除会话。
    """
    monitor.report_tool("RAGFlow 助手问答工具", {"chat_name": chat_name, "question": question})

    session = None
    use_chat = None
    try:
        client = _get_ragflow_client()
        chats = client.list_chats(name=chat_name)
        if not chats:
            return f"没有找到名为 {chat_name} 的 RAGFlow 助手。"

        use_chat = chats[0]
        session = use_chat.create_session(name="deep_search_temp_session")
        response = session.ask(question, stream=True)

        result = ""
        for part in response:
            content = _get_attr(part, "content", "")
            if content:
                result = str(content)

        return result or "RAGFlow 助手没有返回内容。"
    except Exception as exc:
        return f"查询 RAGFlow 助手失败: {exc}"
    finally:
        if use_chat is not None and session is not None:
            try:
                use_chat.delete_sessions(ids=[session.id])
            except Exception as exc:
                print(f"[RAGFlow] 删除临时会话失败: {exc}")
