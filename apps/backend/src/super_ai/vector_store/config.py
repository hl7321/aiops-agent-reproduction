"""只从显式本地 JSON 合并结果构建的 Milvus typed settings。"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from super_ai.project_config import load_project_config
from super_ai.vector_store.errors import VectorStoreConfigurationError

_COLLECTION_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class VectorStoreSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    uri: str
    token: SecretStr = Field(min_length=1)
    collection_name: str = Field(alias="collectionName", min_length=1, max_length=255)

    @field_validator("uri")
    @classmethod
    def _uri_is_http(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("必须是 http/https URI")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("URI 不得包含凭据")
        return normalized

    @field_validator("collection_name")
    @classmethod
    def _collection_name_is_safe(cls, value: str) -> str:
        if _COLLECTION_NAME.fullmatch(value) is None:
            raise ValueError("必须是 Milvus 标识符")
        return value


def load_vector_store_settings(project_path: Path, user_path: Path) -> VectorStoreSettings:
    merged = load_project_config(project_path, user_path)
    try:
        return VectorStoreSettings.model_validate(merged.get("vectorStore"))
    except ValidationError as error:
        paths = sorted(
            {
                "vectorStore."
                + ".".join(str(item) for item in issue["loc"])
                for issue in error.errors(
                    include_url=False,
                    include_context=False,
                    include_input=False,
                )
            }
        )
        raise VectorStoreConfigurationError(
            f"向量存储配置校验失败: {', '.join(paths)}"
        ) from error
