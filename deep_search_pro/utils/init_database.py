"""
将数据库txt文件信息的表创建插入数据
"""

import os
import mysql.connector
from mysql.connector import Error
from dotenv import load_dotenv

load_dotenv()

def execute_sql_file(file_path, connection):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    current_statement = ""
    cursor = connection.cursor()
    executed_count = 0
    
    for line in lines:
        stripped_line = line.strip()
        
        if not stripped_line or stripped_line.startswith('--'):
            continue
        
        current_statement += line
        
        if ';' in line:
            try:
                statements = current_statement.split(';')
                for stmt in statements:
                    stmt = stmt.strip()
                    if stmt and not stmt.startswith('--'):
                        cursor.execute(stmt)
                        executed_count += 1
                        print(f"✅ 执行成功: {stmt[:50]}..." if len(stmt) > 50 else f"✅ 执行成功: {stmt}")
            except Error as e:
                print(f"❌ 执行失败: {current_statement[:50]}...")
                print(f"   错误: {e}")
                raise
            finally:
                current_statement = ""
    
    connection.commit()
    cursor.close()
    return executed_count

def main():
    try:
        db_config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'port': int(os.getenv('MYSQL_PORT', '3306')),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', '123456'),
            'database': None
        }
        
        print("🔌 正在连接 MySQL 数据库...")
        connection = mysql.connector.connect(**db_config)
        
        if connection.is_connected():
            print("✅ 数据库连接成功！")
            
            sql_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '数据库脚本.txt')
            
            if not os.path.exists(sql_file_path):
                print(f"❌ 未找到数据库脚本文件: {sql_file_path}")
                return
            
            print(f"📄 正在读取 SQL 脚本: {sql_file_path}")
            count = execute_sql_file(sql_file_path, connection)
            print(f"\n🎉 执行完成！共执行 {count} 条 SQL 语句")
            
            cursor = connection.cursor()
            cursor.execute("USE pharma_db")
            
            cursor.execute("SELECT COUNT(*) FROM drugs")
            drug_count = cursor.fetchone()[0]
            print(f"📊 药品表: {drug_count} 条记录")
            
            cursor.execute("SELECT COUNT(*) FROM inventory")
            inv_count = cursor.fetchone()[0]
            print(f"📊 库存表: {inv_count} 条记录")
            
            cursor.execute("SELECT COUNT(*) FROM sales_records")
            sales_count = cursor.fetchone()[0]
            print(f"📊 销售记录表: {sales_count} 条记录")
            
            cursor.close()
            
        connection.close()
        print("\n🔌 数据库连接已关闭")
        
    except Error as e:
        print(f"❌ 数据库操作失败: {e}")
        print("\n💡 请检查：")
        print("   1. MySQL 服务是否已启动")
        print("   2. 数据库连接信息是否正确 (.env 文件)")
        print("   3. MySQL 用户是否有创建数据库的权限")

if __name__ == "__main__":
    main()