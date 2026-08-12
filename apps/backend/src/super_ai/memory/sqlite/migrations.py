"""测试和显式初始化路径使用的 Alembic helper。"""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

_BACKEND_ROOT = Path(__file__).resolve().parents[4]
_ALEMBIC_INI = _BACKEND_ROOT / "alembic.ini"


async def upgrade_database(database_url: str, revision: str = "head") -> None:
    """在线程中把显式数据库 URL 升级到指定 revision。"""
    configuration = Config(str(_ALEMBIC_INI))
    configuration.attributes["database_url"] = database_url
    await asyncio.to_thread(command.upgrade, configuration, revision)
