"""
数据库的智能体，具有查询表名，表结构，表数据的功能
"""

from agent.prompts import sub_agents_content
from tools.db_tools import list_sql_tables,get_table_data,execute_sql_query

#组装agent
database_query_agent={
    "name": sub_agents_content["db"]["name"],
    "description": sub_agents_content["db"]["description"],
    "tools": [list_sql_tables,get_table_data,execute_sql_query],
    "system_prompt": sub_agents_content["db"]["system_prompt"],

}






