import csv
import io
import os
import re
from typing import Annotated, Iterable

from dotenv import load_dotenv
from langchain_core.tools import tool

from api.monitor import monitor

try:
    from mysql.connector import Error, connect
except ImportError:
    Error = Exception
    connect = None


load_dotenv()

IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")
READ_ONLY_SQL_RE = re.compile(r"^\s*(select|show|describe|desc|with)\b", re.IGNORECASE | re.DOTALL)


def get_db_config() -> dict:
    if connect is None:
        raise RuntimeError("未安装 mysql-connector-python，无法使用数据库工具")

    config = {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": os.getenv("MYSQL_DATABASE"),
        "charset": os.getenv("MYSQL_CHARSET", "utf8mb4"),
        "collation": os.getenv("MYSQL_COLLATION", "utf8mb4_unicode_ci"),
        "autocommit": True,
        "sql_mode": os.getenv("MYSQL_SQL_MODE", "TRADITIONAL"),
    }
    config = {key: value for key, value in config.items() if value is not None}

    missing_keys = [key for key in ("user", "password", "database") if key not in config]
    if missing_keys:
        raise RuntimeError(f"缺少数据库配置: {', '.join(missing_keys)}")

    return config


def _quote_identifier(identifier: str) -> str:
    if not IDENTIFIER_RE.fullmatch(identifier or ""):
        raise ValueError(f"非法表名: {identifier}")
    return f"`{identifier}`"


def _rows_to_csv(columns: Iterable[str], rows: Iterable[tuple]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([str(column) for column in columns])
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    return output.getvalue().strip()


def _ensure_read_only_query(query: str) -> str:
    sql = (query or "").strip()
    if not sql:
        raise ValueError("SQL 不能为空")
    if ";" in sql.rstrip(";"):
        raise ValueError("不允许一次执行多条 SQL")
    sql = sql.rstrip(";")
    if not READ_ONLY_SQL_RE.match(sql):
        raise ValueError("只允许执行 SELECT/SHOW/DESCRIBE 等只读 SQL")
    return sql


@tool
def list_sql_tables() -> str:
    """
    查询当前 MySQL 数据库中的可用表名。
    在读取表数据或执行自定义 SQL 前，应先调用本工具了解数据库结构。
    """
    monitor.report_tool("数据库表名查询工具", {})

    try:
        with connect(**get_db_config()) as conn:
            with conn.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = [row[0] for row in cursor.fetchall()]
                if not tables:
                    return "数据库中没有可用表。"
                return "可用表: " + ", ".join(map(str, tables))
    except Exception as exc:
        return f"查询数据库表失败: {exc}"


@tool
def get_table_data(
    table_name: Annotated[str, "要读取的表名，必须来自 list_sql_tables 的返回结果"],
    limit: Annotated[int, "最多返回多少行数据"] = 100,
) -> str:
    """
    读取指定表的前若干行数据，返回 CSV 文本。
    """
    monitor.report_tool("数据库表数据查询工具", {"table_name": table_name, "limit": limit})

    try:
        safe_table = _quote_identifier(table_name)
        safe_limit = max(1, min(int(limit), 500))
        with connect(**get_db_config()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(f"SELECT * FROM {safe_table} LIMIT %s", (safe_limit,))
                if not cursor.description:
                    return f"{table_name} 没有可读取的列。"
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return _rows_to_csv(columns, rows) if rows else ",".join(columns) + "\n"
    except Exception as exc:
        return f"查询数据库表数据失败: {exc}"


@tool
def execute_sql_query(
    query: Annotated[str, "只读 SQL 查询，允许 SELECT/SHOW/DESCRIBE/WITH，不允许增删改"],
) -> str:
    """
    执行自定义只读 SQL 查询并返回 CSV 文本。
    复杂筛选、关联和聚合可以使用本工具，但禁止写入或删除数据。
    """
    monitor.report_tool("数据库自定义 SQL 查询工具", {"query": query})

    try:
        sql = _ensure_read_only_query(query)
        with connect(**get_db_config()) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
                if not cursor.description:
                    return "SQL 执行成功，但没有返回列。"
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                return _rows_to_csv(columns, rows) if rows else ",".join(columns) + "\n"
    except Exception as exc:
        return f"执行 SQL 查询失败: {exc}"
