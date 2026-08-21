"""Alembic async migration environment。"""

from __future__ import annotations

import asyncio
import importlib
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from super_ai.memory.config import load_database_settings
from super_ai.memory.sqlite.base import Base
from super_ai.memory.sqlite.paths import ensure_sqlite_parent_directory

configuration = context.config
if configuration.config_file_name is not None:
    fileConfig(configuration.config_file_name, disable_existing_loggers=False)

importlib.import_module("super_ai.memory.extended_sqlite.auth_models")
importlib.import_module("super_ai.memory.extended_sqlite.background_job_models")
importlib.import_module("super_ai.memory.extended_sqlite.knowledge_models")
importlib.import_module("super_ai.memory.extended_sqlite.document_index_task_models")
importlib.import_module("super_ai.memory.extended_sqlite.chat_models")
importlib.import_module("super_ai.memory.extended_sqlite.agent_audit_models")
importlib.import_module("super_ai.memory.extended_sqlite.chat_configuration_models")
importlib.import_module("super_ai.memory.extended_sqlite.mcp_connection_models")
importlib.import_module("super_ai.memory.extended_sqlite.diagnostic_models")
target_metadata = Base.metadata


def _database_url() -> str:
    injected = configuration.attributes.get("database_url")
    if isinstance(injected, str) and injected:
        return injected
    repository_root = Path(__file__).resolve().parents[3]
    settings = load_database_settings(
        repository_root / "config/project.json",
        repository_root / "config/user.project.json",
    )
    return settings.url


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def _run_migrations_online() -> None:
    section = configuration.get_section(configuration.config_ini_section) or {}
    database_url = _database_url()
    ensure_sqlite_parent_directory(database_url)
    section["sqlalchemy.url"] = database_url
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(_run_migrations_online())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
