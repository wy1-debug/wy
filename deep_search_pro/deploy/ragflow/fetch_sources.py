"""Fetch pinned official deployment references; never fetch application secrets."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
import requests

ROOT = Path(__file__).resolve().parent
BASE = "https://raw.githubusercontent.com/infiniflow/ragflow/v0.26.0/"
FILES = {
    "docker/init.sql": "init.sql",
    "api/apps/restful_apis/user_api.py": "reference/user_app.py",
    "api/apps/llm_app.py": "reference/llm_app.py",
    "api/apps/restful_apis/system_api.py": "reference/system_app.py",
    "api/db/services/user_service.py": "reference/user_service.py",
    "common/versions.py": "reference/versions.py",
    "common/settings.py": "reference/settings.py",
    "api/db/joint_services/user_account_service.py": "reference/user_account_service.py",
    "api/db/services/tenant_llm_service.py": "reference/tenant_llm_service.py",
    "api/utils/crypt.py": "reference/crypt.py",
    "api/apps/restful_apis/provider_api.py": "reference/provider_api.py",
    "api/apps/services/provider_api_service.py": "reference/provider_api_service.py",
    "api/apps/restful_apis/models_api.py": "reference/models_api.py",
    "api/apps/services/models_api_service.py": "reference/models_api_service.py",
    "api/apps/__init__.py": "reference/apps_init.py",
    "api/apps/restful_apis/dataset_api.py": "reference/dataset_api.py",
    "api/apps/services/dataset_api_service.py": "reference/dataset_api_service.py",
    "conf/public.pem": "public.pem",
}


def fetch(item):
    source, destination = item
    path = ROOT / destination
    if path.exists():
        return f"cached: {source}"
    for attempt in range(3):
        try:
            response = requests.get(BASE + source, timeout=(10, 30))
            response.raise_for_status()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(response.text, encoding="utf-8", newline="\n")
            return f"saved: {source}"
        except requests.RequestException as exc:
            if attempt == 2:
                return f"failed: {source}: {type(exc).__name__}"
            time.sleep(1)


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(fetch, FILES.items()):
            print(result, flush=True)
