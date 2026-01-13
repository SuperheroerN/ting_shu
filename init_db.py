"""
MySQL数据库自动初始化脚本
自动创建数据库和所有需要的表

使用步骤：
1. 修改 config.py 中的数据库配置（用户名、密码等）
2. 安装依赖: pip install Flask-SQLAlchemy pymysql
3. 运行此脚本: python init_db.py

脚本会自动：
- 检查并创建数据库（如果不存在）
- 创建所有需要的表
- 显示创建结果
"""
import pymysql
from app import app
from models.database import db
from config import MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD, MYSQL_HOST, MYSQL_PORT

def create_database_if_not_exists():
    """如果数据库不存在，则创建它"""
    try:
        print("\n正在检查数据库是否存在...")
        # 连接到MySQL服务器（不指定数据库）
        connection = pymysql.connect(
            host=MYSQL_HOST,
            port=int(MYSQL_PORT),
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            charset='utf8mb4'
        )
        
        with connection.cursor() as cursor:
            # 检查数据库是否存在
            cursor.execute(f"SHOW DATABASES LIKE '{MYSQL_DATABASE}'")
            result = cursor.fetchone()
            
            if result:
                print(f"✓ 数据库 '{MYSQL_DATABASE}' 已存在")
            else:
                print(f"数据库 '{MYSQL_DATABASE}' 不存在，正在创建...")
                # 创建数据库
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{MYSQL_DATABASE}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
                connection.commit()
                print(f"✓ 数据库 '{MYSQL_DATABASE}' 创建成功！")
        
        connection.close()
        return True
        
    except pymysql.Error as e:
        print(f"✗ 创建数据库失败: {e}")
        print("\n可能的原因:")
        print("1. MySQL服务未运行")
        print("2. 用户名或密码错误")
        print("3. 用户没有创建数据库的权限")
        return False
    except Exception as e:
        print(f"✗ 连接MySQL服务器失败: {e}")
        return False

def init_database():
    """初始化数据库"""
    print("=" * 60)
    print("MySQL数据库自动初始化")
    print("=" * 60)
    print(f"数据库配置:")
    print(f"  主机: {MYSQL_HOST}")
    print(f"  端口: {MYSQL_PORT}")
    print(f"  用户: {MYSQL_USER}")
    print(f"  密码: {'*' * len(MYSQL_PASSWORD) if MYSQL_PASSWORD else '(空)'}")
    print(f"  数据库: {MYSQL_DATABASE}")
    print("=" * 60)
    
    # 第一步：创建数据库（如果不存在）
    if not create_database_if_not_exists():
        print("\n" + "=" * 60)
        print("✗ 数据库初始化失败！")
        print("=" * 60)
        return
    
    # 第二步：创建表
    with app.app_context():
        try:
            # 测试数据库连接
            print("\n正在连接数据库...")
            db.engine.connect()
            print("✓ 数据库连接成功！")
            
            # 创建所有表
            print("\n正在创建数据表...")
            db.create_all()
            
            # 检查表是否创建成功
            print("\n正在验证表创建...")
            inspector = db.inspect(db.engine)
            existing_tables = inspector.get_table_names()
            
            expected_tables = [
                'users',
                'bookshelf',
                'play_history',
                'api_config',
                'ip_access_log',
                'ip_blacklist',
                'announcement',
                'ip_announcement_confirm',
                'feedback',
                'app_config',
                'interface_definition'
            ]
            
            created_tables = []
            missing_tables = []
            
            for table in expected_tables:
                if table in existing_tables:
                    created_tables.append(table)
                else:
                    missing_tables.append(table)
            
            print("\n" + "=" * 60)
            if not missing_tables:
                print("✓ 数据库初始化完成！")
            else:
                print("⚠ 数据库初始化部分完成！")
            print("=" * 60)
            print(f"数据库名称: {MYSQL_DATABASE}")
            print(f"\n已创建的表 ({len(created_tables)}/{len(expected_tables)}):")
            for table in created_tables:
                print(f"  ✓ {table}")
            
            if missing_tables:
                print(f"\n未创建的表 ({len(missing_tables)}):")
                for table in missing_tables:
                    print(f"  ✗ {table}")
            
            print("\n" + "=" * 60)
            print("下一步操作:")
            print("1. 启动应用: python app.py")
            print("2. 初始化API配置: python init_admin_config.py")
            print("=" * 60)
            
        except Exception as e:
            print("\n" + "=" * 60)
            print("✗ 创建数据表失败！")
            print("=" * 60)
            print(f"错误信息: {e}")
            print("\n请检查以下事项:")
            print("1. MySQL服务是否正在运行")
            print("2. config.py 中的数据库配置是否正确")
            print("3. 用户是否有创建表的权限")
            print("4. 是否已安装依赖包: pip install Flask-SQLAlchemy pymysql")
            print("=" * 60)
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    init_database()
