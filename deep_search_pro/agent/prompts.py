from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).parent.parent
PROMPT_FILE = PROJECT_ROOT / "prompt" / "prompts.yml"


def load_yaml(file_path: Path) -> dict[str, Any]:
    with file_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


prompt_yaml_content = load_yaml(PROMPT_FILE)
main_agent_content = prompt_yaml_content["main_agent"]
sub_agents_content = prompt_yaml_content["sub_agents"]
