"""持久化配置的 typed validation。"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from super_ai.project_config import load_project_config


class DatabaseSettings(BaseModel):
    """显式初始化数据库资源所需的最小配置。"""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    url: str = Field(min_length=1)
    echo: bool = False

    @field_validator("url")
    @classmethod
    def validate_sqlalchemy_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("database.url 不得为空")
        try:
            make_url(normalized)
        except ArgumentError as error:
            raise ValueError("database.url 不是有效的 SQLAlchemy URL") from error
        return normalized


class _ProjectDatabaseSettings(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, strict=True)

    database: DatabaseSettings


def load_database_settings(project_path: Path, user_path: Path) -> DatabaseSettings:
    """从两份显式 JSON 路径的深合并结果读取数据库配置。"""
    merged = load_project_config(project_path, user_path)
    return _ProjectDatabaseSettings.model_validate(merged).database
