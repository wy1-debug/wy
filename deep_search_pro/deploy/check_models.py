"""Check configured model access with synthetic text; never print API keys."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from dotenv import dotenv_values

config = dotenv_values(Path(__file__).resolve().parents[1] / ".env")
base = config["OPENAI_BASE_URL"].rstrip("/")
key = config["OPENAI_API_KEY"]
model = config.get("LLM_MODEL") or config.get("LLM_QWEN3") or config.get("LLM_QWEN_MAX")


def check(kind):
    payload = {"model": "text-embedding-v3", "input": "测试知识库连接"} if kind == "embeddings" else {
        "model": model, "messages": [{"role": "user", "content": "只回复 OK"}], "max_tokens": 16,
        "enable_thinking": False,
    }
    try:
        response = requests.post(f"{base}/{kind}", json=payload,
                                 headers={"Authorization": f"Bearer {key}"}, timeout=45)
        result = response.json()
        if response.ok:
            detail = len(result["data"][0]["embedding"]) if kind == "embeddings" else result["choices"][0]["message"]["content"]
        else:
            detail = str(result.get("error", {})).replace(key, "[REDACTED]")[:400]
        return {"check": kind, "status": response.status_code, "result": detail}
    except Exception as exc:
        return {"check": kind, "error": str(exc).replace(key, "[REDACTED]")[:400]}


if __name__ == "__main__":
    with ThreadPoolExecutor(2) as pool:
        for result in pool.map(check, ["embeddings", "chat/completions"]):
            print(result, flush=True)
