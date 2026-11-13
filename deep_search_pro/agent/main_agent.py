import asyncio
import shutil
from pathlib import Path
from typing import Any

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

from agent.llm import model
from agent.prompts import main_agent_content
from agent.subagents.database_query_agent import database_query_agent
from agent.subagents.knowledge_base_agent import knowledge_base_agent
from agent.subagents.network_search_agent import network_search_agent
from api.context import reset_session_context, set_session_context, set_thread_context
from api.monitor import monitor
from tools.markdown_tools import generate_markdown
from tools.pdf_tools import convert_md_to_pdf
from tools.upload_file_read_tool import read_file_content
from utils.upload_storage import session_path


PROJECT_ROOT = Path(__file__).parent.parent.resolve()


main_agent = create_deep_agent(
    model=model,
    system_prompt=main_agent_content["system_prompt"],
    tools=[generate_markdown, convert_md_to_pdf, read_file_content],
    checkpointer=InMemorySaver(),
    subagents=[
        database_query_agent,
        network_search_agent,
        knowledge_base_agent,
    ],
)


def _stringify_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or item))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _format_agent_error(exc: Exception) -> str:
    error_text = str(exc)

    if "invalid_api_key" in error_text or "Incorrect API key" in error_text:
        return "模型 API Key 无效：请在项目 .env 中更新 OPENAI_API_KEY 并重启后端。文件上传已保存，可在同一会话中重试。"

    if "Arrearage" in error_text or "overdue-payment" in error_text or "account is in good standing" in error_text:
        return (
            "模型服务调用失败：DashScope/阿里云百炼账号当前欠费或计费状态异常（Arrearage）。"
            "请先在阿里云控制台结清欠费并恢复账号状态，或在 .env 中更换可用的 OPENAI_API_KEY。"
        )

    if "AllocationQuota.FreeTierOnly" in error_text or "Free quota exhausted" in error_text:
        return (
            "模型服务调用失败：当前模型免费额度已用完。"
            "请在阿里云控制台充值/关闭仅使用免费额度模式，或在 .env 中切换到可用模型。"
        )

    if "access_denied" in error_text or "Access denied" in error_text:
        return (
            "模型服务调用失败：当前 API Key 没有访问该模型的权限。"
            "请检查 DashScope 模型权限，或在 .env 中更换 LLM_MODEL/OPENAI_API_KEY。"
        )

    if "enable_thinking must be set to false" in error_text:
        return "模型服务调用失败：qwen3 非流式调用需要关闭 thinking，请确认 agent/llm.py 已加载最新配置。"

    if "Connection error" in error_text:
        return "模型服务连接失败：请检查 OPENAI_BASE_URL、网络代理、防火墙或本机是否能访问模型服务地址。"

    return f"执行主智能体异常: {error_text}"


def _copy_uploaded_files(session_id: str, session_dir: Path) -> list[str]:
    upload_dir = session_path(PROJECT_ROOT / "updated", session_id)
    if not upload_dir.exists():
        return []

    copied_files: list[str] = []
    for source in upload_dir.iterdir():
        if not source.is_file():
            continue

        target = session_dir / source.name
        shutil.copy2(source, target)
        copied_files.append(source.name)

    return copied_files


async def run_deep_agent(task_query: str, session_id: str) -> None:
    """
    Run the main agent for one browser task and stream progress through monitor.
    """
    print(f"[Agent] 会话开始: {session_id}")

    session_dir = session_path(PROJECT_ROOT / "output", session_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    session_dir_str = str(session_dir).replace("\\", "/")
    relative_session_dir = str(session_dir.relative_to(PROJECT_ROOT)).replace("\\", "/")

    uploaded_files = _copy_uploaded_files(session_id, session_dir)
    if uploaded_files:
        uploaded_info_prompt = (
            "\n[已上传文件]\n"
            "这些文件已经复制到当前工作目录，请优先使用 read_file_content 工具读取并参考：\n"
            + "\n".join(f"- {name}" for name in uploaded_files)
            + "\n"
        )
    else:
        uploaded_info_prompt = ""

    session_dir_token = set_session_context(session_dir_str)
    thread_id_token = set_thread_context(session_id)
    monitor.report_session_dir(session_dir_str)

    config = {"configurable": {"thread_id": session_id}}
    path_instruction = f"""

[工作环境指令]
工作目录: {relative_session_dir}
{uploaded_info_prompt}
规则:
1. 新生成文件必须保存到工作目录内，例如: {relative_session_dir}/report.md。
2. 读取已上传文件时，直接把文件名作为 filename 参数传给 read_file_content，例如: sample.txt。
3. 使用相对路径，不要使用绝对路径。
4. 如果存在上传文件，请先分析文件内容，再回答或生成文档。
"""

    try:
        async for chunk in main_agent.astream(
            input={
                "messages": [
                    {
                        "role": "user",
                        "content": f"{task_query}\n{path_instruction}",
                    }
                ]
            },
            config=config,
        ):
            for node_name, state in chunk.items():
                if not state or "messages" not in state:
                    continue

                messages = state["messages"]
                if not isinstance(messages, list) or not messages:
                    continue

                last_msg = messages[-1]
                tool_calls = getattr(last_msg, "tool_calls", None)
                if node_name == "model" and tool_calls:
                    for tool_call in tool_calls:
                        name = tool_call.get("name") if isinstance(tool_call, dict) else getattr(tool_call, "name", None)
                        args = tool_call.get("args", {}) if isinstance(tool_call, dict) else getattr(tool_call, "args", {})
                        if name == "task":
                            monitor.report_assistant(
                                args.get("subagent_type", "未知助手"),
                                {"description": args.get("description", "")},
                            )
                    continue

                content = _stringify_message_content(getattr(last_msg, "content", ""))
                if node_name == "model" and content.strip():
                    print(f"[Agent] 最终结果: {content[:100]}")
                    monitor.report_task_result(content)

    except asyncio.CancelledError:
        monitor._emit("cancelled", "任务已取消")
        raise
    except Exception as exc:
        monitor.report_error(_format_agent_error(exc))
    finally:
        reset_session_context(session_dir_token, thread_id_token)
