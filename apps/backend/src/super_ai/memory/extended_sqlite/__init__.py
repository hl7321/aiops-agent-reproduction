"""SQLite 的可扩展 repository adapter，不在导入时创建数据库资源。"""

from super_ai.memory.extended_sqlite.repository import SqliteRepository

__all__ = ["SqliteRepository"]
