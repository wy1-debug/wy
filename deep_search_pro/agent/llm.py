import os

from dotenv import find_dotenv, load_dotenv
from langchain_openai import ChatOpenAI


load_dotenv(find_dotenv())


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise RuntimeError(f"Missing required environment variable, expected one of: {', '.join(names)}")


model_name = _first_env("LLM_MODEL", "LLM_QWEN3", "LLM_QWEN_MAX")
api_key = _require_env("OPENAI_API_KEY")
base_url = (os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE") or "").strip()
if not base_url:
    raise RuntimeError("Missing required environment variable: OPENAI_BASE_URL")

# Keep compatibility with integrations that still look for OPENAI_API_BASE.
os.environ.setdefault("OPENAI_API_BASE", base_url)

model_kwargs = {}
if model_name.startswith("qwen3"):
    model_kwargs["extra_body"] = {"enable_thinking": False}

model = ChatOpenAI(
    model=model_name,
    api_key=api_key,
    base_url=base_url,
    timeout=60,
    max_retries=2,
    **model_kwargs,
)
