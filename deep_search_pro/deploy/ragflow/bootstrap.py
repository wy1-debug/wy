"""Initialize the local account, API key and empty dataset, without an LLM call.

Run from the project directory: python deploy/ragflow/bootstrap.py
Account credentials are written locally and never printed.
"""
import base64
import json
import secrets
import shutil
import sys
from pathlib import Path

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from dotenv import set_key

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:9380/api/v1"
ACCOUNT_PATH = HERE / "local-account.json"


def checked(response):
    response.raise_for_status()
    data = response.json()
    if data.get("code") != 0:
        raise RuntimeError(data.get("message", "RAGFlow request failed"))
    return data.get("data")


def initialize():
    requests.get(BASE + "/system/ping", timeout=10).raise_for_status()
    if ACCOUNT_PATH.exists():
        account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
    else:
        account = {"email": "admin@deepsearch.local", "password": secrets.token_urlsafe(24),
                   "nickname": "DeepSearch 本地管理员"}
        ACCOUNT_PATH.write_text(json.dumps(account, ensure_ascii=False, indent=2), encoding="utf-8")
    public_key = serialization.load_pem_public_key((HERE / "public.pem").read_bytes())
    ciphertext = public_key.encrypt(base64.b64encode(account["password"].encode()), padding.PKCS1v15())
    payload = {"email": account["email"], "password": base64.b64encode(ciphertext).decode()}
    session = requests.Session()
    login = session.post(BASE + "/auth/login", json=payload, timeout=30)
    result = login.json()
    if result.get("code") != 0 and "not registered" in result.get("message", ""):
        login = session.post(BASE + "/users", json={**payload, "nickname": account["nickname"]}, timeout=60)
    checked(login)
    session.headers["Authorization"] = login.headers["Authorization"]
    tokens = checked(session.get(BASE + "/system/tokens", timeout=30))
    api_key = tokens[0]["token"] if tokens else checked(session.post(BASE + "/system/tokens", timeout=30))["token"]
    account["api_key"] = api_key
    ACCOUNT_PATH.write_text(json.dumps(account, ensure_ascii=False, indent=2), encoding="utf-8")

    # Preserve the original remote configuration; edit only the RAGFlow settings.
    env_path = ROOT / ".env"
    backup = ROOT / ".env.before-local-ragflow"
    if env_path.exists() and not backup.exists():
        shutil.copy2(env_path, backup)
    set_key(env_path, "RAGFLOW_API_URL", "http://127.0.0.1:9380")
    set_key(env_path, "RAGFLOW_API_KEY", api_key)

    # An empty dataset may be created before an embedding model is configured.
    from ragflow_sdk import RAGFlow
    rag = RAGFlow(api_key=api_key, base_url="http://127.0.0.1:9380")
    # 0.26 returns a permission error for a name filter with no existing match.
    datasets = [item for item in rag.list_datasets(page_size=100) if item.name == "DeepSearch 本地知识库"]
    dataset = datasets[0] if datasets else rag.create_dataset(
        name="DeepSearch 本地知识库", description="本地企业文档知识库；配置模型后可解析和检索。", chunk_method="naive")
    account["dataset_id"] = dataset.id
    set_key(env_path, "RAGFLOW_DATASET_ID", dataset.id)
    ACCOUNT_PATH.write_text(json.dumps(account, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Local account, API key and dataset initialized.")
    print("Account details: deploy/ragflow/local-account.json (credentials not printed)")
    print("Dataset:", dataset.name, dataset.id)


if __name__ == "__main__":
    try:
        initialize()
    except Exception as exc:
        message = str(exc)
        if ACCOUNT_PATH.exists():
            account = json.loads(ACCOUNT_PATH.read_text(encoding="utf-8"))
            for name in ("password", "api_key"):
                if account.get(name):
                    message = message.replace(account[name], "[REDACTED]")
        print(f"Initialization incomplete: {message}", file=sys.stderr)
        sys.exit(1)
