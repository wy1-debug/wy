import os
from typing import Annotated, Literal

from dotenv import load_dotenv
from langchain_core.tools import tool

from api.monitor import monitor

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None


load_dotenv()
_tavily_client = None


def _get_tavily_client():
    global _tavily_client
    if _tavily_client is not None:
        return _tavily_client

    if TavilyClient is None:
        raise RuntimeError("未安装 tavily-python，无法使用网络搜索工具")

    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise RuntimeError("缺少 TAVILY_API_KEY 配置")

    _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client


@tool
def internet_search(
    query: Annotated[str, "需要检索的关键词或问题"],
    topic: Annotated[Literal["news", "finance", "general"], "搜索主题类型"] = "general",
    max_results: Annotated[int, "返回结果数量，建议 3 到 8 条"] = 5,
    include_raw_content: Annotated[bool, "是否返回网页原始正文"] = False,
) -> str:
    """
    根据用户问题检索公开互联网信息。
    当问题需要数据库或 RAGFlow 内部知识库时，不要优先使用本工具。
    """
    monitor.report_tool(
        "网络搜索工具",
        {
            "query": query,
            "topic": topic,
            "max_results": max_results,
            "include_raw_content": include_raw_content,
        },
    )

    try:
        client = _get_tavily_client()
        result = client.search(
            query=query,
            topic=topic,
            max_results=max(1, min(int(max_results), 10)),
            include_raw_content=include_raw_content,
        )
        return str(result)
    except Exception as exc:
        return f"网络搜索失败: {exc}"
