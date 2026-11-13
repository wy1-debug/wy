import os
from pathlib import Path
from typing import Optional, Tuple

from dotenv import load_dotenv


def _load_ragflow_env() -> Tuple[Optional[str], Optional[str]]:
    """
    Load RAGFlow configuration from the project .env file and environment.
    """
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

    return os.getenv("RAGFLOW_API_KEY"), os.getenv("RAGFLOW_API_URL")
