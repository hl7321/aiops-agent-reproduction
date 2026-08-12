"""文件型 SQLite 显式初始化所需的路径准备。"""

from pathlib import Path

from sqlalchemy.engine import make_url


def ensure_sqlite_parent_directory(database_url: str) -> None:
    """为文件型 SQLite URL 创建父目录；内存数据库不触碰文件系统。"""
    database = make_url(database_url).database
    if not database or database == ":memory:":
        return
    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)
