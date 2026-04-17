"""
数据库迁移脚本：添加 stt_engine_used 字段到 video_chunks 表
"""
import sqlite3
from pathlib import Path

def migrate_database():
    db_path = Path("./data/interview_ai.db")
    
    if not db_path.exists():
        print("数据库文件不存在，将在应用启动时自动创建")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(video_chunks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'stt_engine_used' not in columns:
            print("添加 stt_engine_used 字段...")
            cursor.execute("""
                ALTER TABLE video_chunks 
                ADD COLUMN stt_engine_used VARCHAR(20)
            """)
            conn.commit()
            print("✓ stt_engine_used 字段添加成功")
        else:
            print("✓ stt_engine_used 字段已存在，无需迁移")
        
    except Exception as e:
        print(f"迁移失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()
