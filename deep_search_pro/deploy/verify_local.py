"""Verify local services and store the deployment guide without parsing it."""
import json
import sys
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rawflow.knowledge_demo import upload_file_to_knowledge
from tools.ragflaw_tools import _get_ragflow_client


def verify():
    config = dotenv_values(ROOT / ".env")
    for name, url in [
        ("application", "http://127.0.0.1:8000/api/health"),
        ("ragflow_ui", "http://127.0.0.1:8080/"),
        ("ragflow_api", "http://127.0.0.1:9380/api/v1/system/ping"),
    ]:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        print(json.dumps({"service": name, "status": response.status_code}))
    client = _get_ragflow_client()
    dataset = client.list_datasets(id=config["RAGFLOW_DATASET_ID"])[0]
    documents = dataset.list_documents()
    if not any(document.name == "DEPLOYMENT.md" for document in documents):
        upload_file_to_knowledge(dataset.id, [ROOT / "DEPLOYMENT.md"], parse=False)
    documents = dataset.list_documents()
    names = [document.name for document in documents]
    assert "DEPLOYMENT.md" in names, names
    print(json.dumps({"dataset": dataset.name, "document_count": len(names),
                      "documents": names, "parsing": "pending_model_configuration"}, ensure_ascii=False))
    print(json.dumps({"available_chats": len(client.list_chats())}))


if __name__ == "__main__":
    verify()
