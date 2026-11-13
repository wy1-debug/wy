from agent.prompts import sub_agents_content
from tools.ragflaw_tools import get_assistant_list,create_ask_delete

knowledge_base_agent = {
    "name": sub_agents_content["ragflow"]["name"],
    "description": sub_agents_content["ragflow"]["description"],
    "tools": [get_assistant_list,create_ask_delete],
    "system_prompt": sub_agents_content["ragflow"]["system_prompt"],
}
