#创建网格搜索智能体
#方法1，dict-》deepagent   方式2：complict-》deepagent

from agent.prompts import sub_agents_content
from tools.tavily_tool import  internet_search

network_search_agent = {
    "name": sub_agents_content["tavily"]["name"],
    "description": sub_agents_content["tavily"]["description"],
    "tools": [internet_search],
    "system_prompt": sub_agents_content["tavily"]["system_prompt"],
}