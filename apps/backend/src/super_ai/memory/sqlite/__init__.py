"""SQLite adapter；所有资源必须由调用方显式创建。"""

from super_ai.memory.sqlite.base import Base, IdTimestampMixin
from super_ai.memory.sqlite.migrations import upgrade_database
from super_ai.memory.sqlite.provider import create_persistence_lifespan, get_session
from super_ai.memory.sqlite.runtime import (
    PersistenceRuntime,
    SessionFactory,
    create_session_factory,
    create_sqlite_engine,
    transaction_scope,
)
from super_ai.memory.sqlite.types import CanonicalJson, UTCDateTime

__all__ = [
    "Base",
    "CanonicalJson",
    "IdTimestampMixin",
    "PersistenceRuntime",
    "SessionFactory",
    "UTCDateTime",
    "create_session_factory",
    "create_sqlite_engine",
    "create_persistence_lifespan",
    "get_session",
    "transaction_scope",
    "upgrade_database",
]
